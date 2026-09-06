#!/usr/bin/env python3
"""Medição real de área e profundidade lógica: RV32I contra RV32IM.

REQ: FR-RV-25 (área por execução real de ferramenta), FR-RV-24 (métricas de
eficiência), NFR-RV-02 (nada é declarado como medido sem rodar a ferramenta),
NFR-RV-03 (comparação sobre a mesma base de código).

Fluxo (specs/decisions.md, ADR-005) -- o `ghdl-yosys-plugin` não está instalado
neste ambiente, então o Verilog é emitido pelo próprio backend de síntese do
GHDL e o Yosys lê esse Verilog:

    ghdl synth --std=08 -gRV32M_ENABLE=<false|true> --out=verilog CPU > cpu_<cfg>.v
    yosys -p 'read_verilog cpu_<cfg>.v; hierarchy -top CPU; proc; memory -nomap;
              opt_expr; techmap; opt_expr; stat'

Duas ressalvas metodológicas, declaradas porque mudam a leitura do número:

1. **Por que a hierarquia NÃO é achatada.** A `entity CPU` não tem porta de
   saída nenhuma (ADR-000). Se o design for achatado, o Yosys corretamente
   conclui que nada é observável e elimina o circuito inteiro -- `synth -top CPU
   -flatten` devolve literalmente 0 células. Mantendo a hierarquia, cada
   submódulo é otimizado em relação às SUAS PRÓPRIAS portas, que são reais, e
   nada é eliminado indevidamente. A área total é a soma dos submódulos, que
   neste design são instanciados uma vez cada.

2. **O que a contagem significa.** São células genéricas do Yosys após
   `techmap` (`$_AND_`, `$_MUX_`, `$_DFF_*_`, ...), não células de um PDK nem
   LUTs de um FPGA específico. Serve para comparar RV32I contra RV32IM no MESMO
   fluxo -- que é exatamente o que a trilha pede --, e não para afirmar área em
   µm².

Profundidade lógica: `ltp -noff` devolve o caminho topológico mais longo entre
registradores, em NÍVEIS DE LÓGICA. É medição estrutural real do Yosys. NÃO é
tempo em nanossegundos: converter níveis em atraso exigiria biblioteca de
células caracterizada, que não existe aqui. Onde este relatório fala em tempo,
fala em ESTIMATIVA e diz isso.

Uso:
    python examples/RISCV32I/tools/synth_ppa.py [--out DIR]

Requer GHDL e Yosys no PATH (na WSL, não no Windows).
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
SRC = EXAMPLE_ROOT / "src"

# Ordem de análise respeitando as dependências de pacote (mesma de rv_build.py)
VHDL_ORDER = [
    "cpu_package.vhd",
    "memory_package.vhd",
    "ALU.vhd",
    "mul_div_unit.vhd",
    "branching_unit.vhd",
    "control_unit.vhd",
    "instruction_decoder.vhd",
    "extend_32.vhd",
    "program_counter.vhd",
    "register_file.vhd",
    "data_ram.vhd",
    "data_rom.vhd",
    "data_memory.vhd",
    "instruction_memory.vhd",
    "fetch_pipeline_register.vhd",
    "decode_pipeline_register.vhd",
    "execute_pipeline_register.vhd",
    "mem_pipeline_register.vhd",
    "hazard_control_unit.vhd",
    "CPU.vhd",
]

CONFIGS = {
    "rv32i": "false",
    "rv32im": "true",
}

# Blocos de ARMAZENAMENTO, separados do núcleo na hora de comparar.
#
# `techmap` expande as memórias em flip-flops e muxes: só a RAM de dados
# (512 bytes = 4096 bits) vira ~93 mil células e sozinha domina o total,
# diluindo a diferença entre RV32I e RV32IM. Como as memórias são IDÊNTICAS nas
# duas configurações, o número que informa a decisão de arquitetura é o do
# NÚCLEO. Os dois totais são reportados; nenhum é escondido.
STORAGE_BLOCKS = {"data_ram", "data_rom", "instruction_memory", "register_file"}

YOSYS_SCRIPT = (
    "read_verilog {v}; "
    "hierarchy -top CPU; "
    "proc; "
    "memory -nomap; "
    "opt_expr; "
    "techmap; "
    "opt_expr; "
    "stat"
)


class ToolError(RuntimeError):
    """Uma ferramenta externa falhou. NUNCA reportamos métrica sem exit 0."""


def _run(cmd: list[str], cwd: Path, stdout_to: Path | None = None) -> str:
    """Executa um comando e falha alto se o exit code não for 0 (NFR-RV-02)."""
    if stdout_to is not None:
        with stdout_to.open("w", encoding="utf-8") as fh:
            proc = subprocess.run(cmd, cwd=cwd, stdout=fh,
                                  stderr=subprocess.PIPE, text=True)
        out = ""
    else:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        out = proc.stdout
    if proc.returncode != 0:
        raise ToolError(
            f"comando falhou (exit {proc.returncode}): {' '.join(cmd)}\n"
            f"stderr:\n{proc.stderr[-4000:]}"
        )
    return out


# --------------------------------------------------------------------------
# Parsing da saída do Yosys
# --------------------------------------------------------------------------

_MODULE_RE = re.compile(r"^=== (\S+) ===\s*$")
_CELLS_RE = re.compile(r"^\s*Number of cells:\s+(\d+)\s*$")
_WIREBITS_RE = re.compile(r"^\s*Number of wire bits:\s+(\d+)\s*$")
_MEMBITS_RE = re.compile(r"^\s*Number of memory bits:\s+(\d+)\s*$")
_CELLTYPE_RE = re.compile(r"^\s{5}(\$\S+)\s+(\d+)\s*$")


@dataclass
class ModuleStat:
    name: str
    cells: int = 0
    wire_bits: int = 0
    memory_bits: int = 0
    cell_types: dict[str, int] = field(default_factory=dict)


def parse_stat(text: str) -> dict[str, ModuleStat]:
    """Extrai as estatísticas por módulo da saída do `stat` do Yosys."""
    mods: dict[str, ModuleStat] = {}
    cur: ModuleStat | None = None
    for line in text.splitlines():
        m = _MODULE_RE.match(line)
        if m:
            name = m.group(1)
            if name == "design":          # cabeçalho "=== design hierarchy ==="
                cur = None
                continue
            cur = ModuleStat(name=name)
            mods[name] = cur
            continue
        if cur is None:
            continue
        m = _CELLS_RE.match(line)
        if m:
            cur.cells = int(m.group(1))
            continue
        m = _WIREBITS_RE.match(line)
        if m:
            cur.wire_bits = int(m.group(1))
            continue
        m = _MEMBITS_RE.match(line)
        if m:
            cur.memory_bits = int(m.group(1))
            continue
        m = _CELLTYPE_RE.match(line)
        if m:
            cur.cell_types[m.group(1)] = int(m.group(2))
    return mods


def friendly(name: str) -> str:
    """`control_unit_5ba93c9...` -> `control_unit`.

    O `ghdl synth` acrescenta ao nome do módulo um hash dos generics, para que
    duas elaborações com generics diferentes não colidam. Para comparar as duas
    configurações lado a lado é preciso remover esse sufixo.
    """
    # Só remove sufixos que são claramente hash (40 dígitos hex) ou um índice de
    # instância APÓS um hash. Um `_\d+$` genérico estragaria `extend_32`.
    n = re.sub(r"_\d+_[0-9a-f]{40}$", "", name)
    n = re.sub(r"_[0-9a-f]{40}$", "", n)
    return n


# --------------------------------------------------------------------------
# Fluxo
# --------------------------------------------------------------------------

def synthesize(cfg: str, enable_m: str, work: Path) -> dict:
    """Sintetiza uma configuração e devolve as métricas medidas."""
    for f in VHDL_ORDER:
        path = SRC / f
        if not path.exists():
            raise ToolError(f"fonte VHDL ausente: {path}")
        _run(["ghdl", "-a", "--std=08", str(path)], cwd=work)

    verilog = work / f"cpu_{cfg}.v"
    _run(["ghdl", "synth", "--std=08", f"-gRV32M_ENABLE={enable_m}",
          "--out=verilog", "CPU"], cwd=work, stdout_to=verilog)

    stat_out = _run(["yosys", "-p", YOSYS_SCRIPT.format(v=verilog.name)], cwd=work)
    (work / f"yosys_{cfg}.log").write_text(stat_out, encoding="utf-8")

    mods = parse_stat(stat_out)
    by_block: dict[str, dict] = {}
    total_cells = 0
    total_mem_bits = 0
    core_cells = 0
    for m in mods.values():
        key = friendly(m.name)
        by_block[key] = {
            "cells": m.cells,
            "wire_bits": m.wire_bits,
            "memory_bits": m.memory_bits,
            "cell_types": m.cell_types,
        }
        total_cells += m.cells
        total_mem_bits += m.memory_bits
        if key not in STORAGE_BLOCKS:
            core_cells += m.cells

    # profundidade lógica dos blocos combinacionais do estágio EX
    depth = {}
    for block in ("alu", "mul_div_unit"):
        real = next((n for n in mods if friendly(n) == block), None)
        if real is None:
            continue
        try:
            out = _run(["yosys", "-p",
                        f"read_verilog {verilog.name}; hierarchy -top CPU; proc; "
                        f"memory -nomap; opt_expr; techmap; "
                        f"select {real}; ltp -noff"], cwd=work)
            mlt = re.search(r"Longest topological path.*?\(length=(\d+)\)", out, re.S)
            if mlt:
                depth[block] = int(mlt.group(1))
        except ToolError:
            pass          # ltp é opcional; ausência é registrada como None

    return {
        "config": cfg,
        "rv32m_enable": enable_m == "true",
        "total_cells": total_cells,
        "core_logic_cells": core_cells,
        "total_memory_bits": total_mem_bits,
        "blocks": by_block,
        "logic_depth_levels": depth,
        "verilog_lines": len(verilog.read_text(encoding="utf-8").splitlines()),
        "measured_by": "ghdl synth --out=verilog + yosys stat (medicao real, ADR-005)",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None,
                    help="diretório de saída (padrão: examples/RISCV32I/ppa)")
    ap.add_argument("--work", default="/tmp/spechdl_synth",
                    help="diretório de trabalho da síntese")
    args = ap.parse_args()

    for tool in ("ghdl", "yosys"):
        if shutil.which(tool) is None:
            print(f"ERRO: '{tool}' não encontrado no PATH. "
                  f"Este script só roda no ambiente Linux/WSL.", file=sys.stderr)
            return 2

    out_dir = Path(args.out) if args.out else EXAMPLE_ROOT / "ppa"
    out_dir.mkdir(parents=True, exist_ok=True)

    results = {}
    for cfg, enable_m in CONFIGS.items():
        work = Path(args.work) / cfg
        if work.exists():
            shutil.rmtree(work)
        work.mkdir(parents=True, exist_ok=True)
        print(f"[synth] {cfg}: RV32M_ENABLE={enable_m} ...", flush=True)
        results[cfg] = synthesize(cfg, enable_m, work)
        print(f"[synth] {cfg}: {results[cfg]['total_cells']} células", flush=True)

    base, ext = results["rv32i"], results["rv32im"]
    blocks = sorted(set(base["blocks"]) | set(ext["blocks"]))
    comparison = {
        "total_cells_rv32i": base["total_cells"],
        "total_cells_rv32im": ext["total_cells"],
        "delta_cells": ext["total_cells"] - base["total_cells"],
        "ratio": (round(ext["total_cells"] / base["total_cells"], 4)
                  if base["total_cells"] else None),
        "core_logic_cells_rv32i": base["core_logic_cells"],
        "core_logic_cells_rv32im": ext["core_logic_cells"],
        "delta_core_logic_cells": ext["core_logic_cells"] - base["core_logic_cells"],
        "core_logic_ratio": (round(ext["core_logic_cells"] / base["core_logic_cells"], 4)
                             if base["core_logic_cells"] else None),
        "storage_blocks_excluded_from_core": sorted(STORAGE_BLOCKS),
        "per_block": {
            b: {
                "rv32i": base["blocks"].get(b, {}).get("cells", 0),
                "rv32im": ext["blocks"].get(b, {}).get("cells", 0),
                "delta": (ext["blocks"].get(b, {}).get("cells", 0)
                          - base["blocks"].get(b, {}).get("cells", 0)),
            }
            for b in blocks
        },
        "logic_depth_levels": {
            "rv32i": base["logic_depth_levels"],
            "rv32im": ext["logic_depth_levels"],
        },
    }

    payload = {
        "requirements": ["FR-RV-24", "FR-RV-25", "NFR-RV-02", "NFR-RV-03"],
        "method": {
            "synthesis": "ghdl synth --std=08 --out=verilog CPU",
            "stat": YOSYS_SCRIPT.format(v="cpu_<cfg>.v"),
            "why_not_flattened":
                "a entity CPU nao tem porta de saida; achatada, o Yosys elimina "
                "o design inteiro (0 celulas). Mantendo a hierarquia, cada "
                "submodulo e otimizado contra as proprias portas.",
            "cell_meaning":
                "celulas genericas do Yosys apos techmap; comparaveis entre as "
                "duas configuracoes no mesmo fluxo, NAO equivalentes a area em "
                "um PDK nem a LUTs de FPGA",
            "depth_meaning":
                "ltp -noff: caminho topologico mais longo em NIVEIS DE LOGICA. "
                "Medicao estrutural real; nao e atraso em nanossegundos.",
        },
        "configs": results,
        "comparison": comparison,
    }

    json_path = out_dir / "ppa.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nescrito: {json_path}")

    print(f"\n{'bloco':<32} {'RV32I':>8} {'RV32IM':>8} {'delta':>8}")
    print("-" * 60)
    for b, v in sorted(comparison["per_block"].items(),
                       key=lambda kv: -abs(kv[1]["delta"])):
        if v["rv32i"] or v["rv32im"]:
            print(f"{b:<32} {v['rv32i']:>8} {v['rv32im']:>8} {v['delta']:>+8}")
    print("-" * 60)
    print(f"{'TOTAL (com memorias)':<32} {base['total_cells']:>8} "
          f"{ext['total_cells']:>8} {comparison['delta_cells']:>+8}")
    print(f"{'NUCLEO (sem memorias)':<32} {base['core_logic_cells']:>8} "
          f"{ext['core_logic_cells']:>8} {comparison['delta_core_logic_cells']:>+8}")
    print(f"\nprofundidade logica (niveis): {comparison['logic_depth_levels']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
