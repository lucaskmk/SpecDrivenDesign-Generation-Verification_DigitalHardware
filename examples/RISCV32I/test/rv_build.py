#!/usr/bin/env python3
"""Driver pytest: monta um programa, gera a imagem `.ram` e roda no GHDL.

REQ: FR-RV-09 (imagem consumida pela ROM), FR-RV-21 (execução real com exit
code), FR-RV-16 (seleção de RV32M por generic), NFR-RV-01 (GHDL + cocotb),
NFR-RV-02 (nada é declarado como medido sem executar a ferramenta).

Cada chamada de `run_program` dispara uma execução real de `ghdl -r` via
`cocotb_tools.runner`. Se o GHDL falhar ou o testbench reprovar,
`runner.test` levanta exceção e o pytest falha.

Nota de desempenho: o GHDL aplica generics na ELABORAÇÃO, que no backend
mcode acontece em `ghdl -r`. Por isso o design é compilado uma única vez por
árvore de fontes (cache abaixo) e cada programa é apenas uma execução nova
com `-gROM_INIT_FILE=...`. Sem esse cache, cada caso de teste recompilaria os
19 arquivos VHDL.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from cocotb_tools.runner import VHDL, get_runner

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
REPO_ROOT = EXAMPLE_ROOT.parent.parent
SRC = EXAMPLE_ROOT / "src"
TOOLS = EXAMPLE_ROOT / "tools"
PROGRAMS = EXAMPLE_ROOT / "programs"

sys.path.insert(0, str(TOOLS))

from rv_assembler import (  # noqa: E402
    assemble_with_symbols,
    find_halt_addresses,
    write_ram_image,
)

# Ordem de análise respeitando as dependências de pacote do design original.
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

# Endereços de RAM usados pelos programas de teste para publicar resultados.
# DATA_RAM_BASE_ADDRESS = 0x00FC8100 (memory_package.vhd)
RAM_BASE = 0x00FC8100
RESULT_SLOT_0 = RAM_BASE
DATA_RAM_SIZE_BYTES = 512
STACK_TOP = RAM_BASE + DATA_RAM_SIZE_BYTES

DEFAULT_ROM_SIZE_WORDS = 1024

ORIGINAL_REVISION = "f884a4e"
"""Commit que vendorizou o design RV32I original (ver decisions.md, ADR-000)."""

# Raiz dos builds. Fica no filesystem do WSL de propósito: compilar dentro de
# /mnt/c é significativamente mais lento.
_BUILD_ROOT = Path(os.environ.get("RV_BUILD_ROOT", Path.home() / "rv32_build_cache"))
_build_cache: dict[tuple[str, str], tuple[Path, object]] = {}


def vhdl_sources(src_dir: Path | None = None) -> list[Path]:
    """Fontes existentes, na ordem de análise.

    `src_dir` permite apontar para uma árvore alternativa — usada para
    materializar o RTL ORIGINAL a partir do git e comparar comportamento
    (FR-RV-07).
    """
    d = src_dir or SRC
    return [d / f for f in VHDL_ORDER if (d / f).exists()]


def result_addr(slot: int) -> int:
    """Endereço do slot de resultado `slot` (palavras de 32 bits)."""
    return RESULT_SLOT_0 + 4 * slot


def design_has_generic(generic_name: str, src_dir: Path | None = None) -> bool:
    """Descobre se `CPU.vhd` já declara o generic pedido."""
    d = src_dir or SRC
    text = (d / "CPU.vhd").read_text(encoding="utf-8", errors="replace")
    head = text.split("end CPU", 1)[0]
    return generic_name.lower() in head.lower()


def _sources_stamp(sources: list[Path]) -> str:
    h = hashlib.sha256()
    for p in sources:
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


def ensure_build(src_dir: Path | None = None) -> tuple[Path, object]:
    """Compila o design uma vez e devolve (diretório de build, runner).

    O runner é reaproveitado porque `cocotb_tools.runner` guarda nele o
    estado das fontes definido em `build()`, exigido depois por `test()`.
    O cache é invalidado automaticamente quando qualquer fonte muda de
    tamanho ou data de modificação.
    """
    sources = vhdl_sources(src_dir)
    if not sources:
        raise RuntimeError(f"nenhum fonte VHDL encontrado em {src_dir or SRC}")

    stamp = _sources_stamp(sources)
    key = (str(src_dir or SRC), stamp)
    cached = _build_cache.get(key)
    if cached is not None and cached[0].exists():
        return cached

    build_dir = _BUILD_ROOT / f"build_{stamp}"
    build_dir.mkdir(parents=True, exist_ok=True)

    runner = get_runner("ghdl")
    runner.build(
        sources=[VHDL(p) for p in sources],
        hdl_toplevel="cpu",
        build_args=["--std=08"],
        build_dir=build_dir,
        always=True,
    )
    _build_cache[key] = (build_dir, runner)
    return build_dir, runner


@dataclass
class ProgramRun:
    """Resultado de uma execução real no GHDL."""

    name: str
    metrics: dict
    image_path: Path
    run_dir: Path
    waveform: Path | None

    @property
    def cycles(self) -> int:
        return self.metrics["cycles"]

    @property
    def instructions(self) -> int:
        return self.metrics["instructions"]

    @property
    def cpi(self) -> float | None:
        return self.metrics["cpi"]


def _run_dir(base: Path, name: str) -> Path:
    d = base / f"run_{name}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _test_env(spec_path: Path) -> dict:
    env = dict(os.environ)
    env["RV_PROGRAM_SPEC"] = str(spec_path)
    env["PYTHONPATH"] = os.pathsep.join(
        [str(HERE), str(TOOLS), env.get("PYTHONPATH", "")]
    )
    return env


def run_program(
    tmp_path: Path,
    name: str,
    asm: str,
    *,
    expect_regs: dict[int, int] | None = None,
    expect_ram: dict[int, int] | None = None,
    max_cycles: int = 20000,
    rv32m: bool = False,
    allow_m: bool | None = None,
    requirements: list[str] | None = None,
    rom_size_words: int = DEFAULT_ROM_SIZE_WORDS,
    waves: bool = False,
    keep_image_at: Path | None = None,
    src_dir: Path | None = None,
    dump_ram: tuple[int, int] | None = None,
) -> ProgramRun:
    """Monta `asm`, grava a imagem `.ram` e executa a CPU no GHDL.

    `rv32m` seleciona o generic `RV32M_ENABLE` do design.
    `allow_m` controla se o MONTADOR aceita instruções RV32M; por padrão
    acompanha `rv32m`, de modo que um programa de baseline não consegue,
    nem por acidente, usar a extensão M (FR-RV-19).
    `dump_ram=(endereço, n_palavras)` faz o testbench devolver o conteúdo da
    RAM em `metrics["ram_dump"]`, usado para provar que as versões RV32I e
    RV32IM de um mesmo benchmark calculam o mesmo resultado (FR-RV-06).
    """
    if allow_m is None:
        allow_m = rv32m

    words, symbols = assemble_with_symbols(asm, base_address=0, allow_m=allow_m)
    if len(words) > rom_size_words:
        raise ValueError(
            f"programa {name!r} tem {len(words)} palavras, "
            f"maior que ROM_SIZE_WORDS={rom_size_words}"
        )

    # Endereços de término: instruções de auto-laço presentes na imagem.
    # REQ: FR-RV-21 -- término determinístico, sem depender de PC estacionário
    # (a CPU resolve saltos em EX, ver ADR-000).
    halt_pcs = find_halt_addresses(words)
    if not halt_pcs:
        raise ValueError(
            f"programa {name!r} não tem instrução de parada. Termine o "
            f"programa com um auto-laço (`halt: j halt`), conforme a "
            f"convenção do ADR-003."
        )

    run_dir = _run_dir(tmp_path, name)
    image = write_ram_image(
        words,
        run_dir / f"{name}.ram",
        header=f"programa: {name}\n"
               f"requisitos: {', '.join(requirements or [])}\n"
               f"palavras: {len(words)}   parada em: "
               f"{', '.join(hex(p) for p in halt_pcs)}\n"
               f"gerado por examples/RISCV32I/tools/rv_assembler.py",
    )
    if keep_image_at is not None:
        keep_image_at.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, keep_image_at)

    metrics_out = run_dir / "metrics.json"
    spec = {
        "name": name,
        "image": str(image),
        "max_cycles": max_cycles,
        "rv32m_enable": rv32m,
        "requirements": requirements or [],
        "halt_pcs": halt_pcs,
        "symbols": symbols,
        "expect_regs": {str(k): v for k, v in (expect_regs or {}).items()},
        "expect_ram": {hex(k): v for k, v in (expect_ram or {}).items()},
        "metrics_out": str(metrics_out),
    }
    if dump_ram is not None:
        # (endereço inicial, quantidade de palavras) -- ver tb_program.py
        spec["dump_ram"] = {"start": dump_ram[0], "count": dump_ram[1]}
    spec_path = run_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    build_dir, runner = ensure_build(src_dir)

    parameters: dict[str, object] = {
        "ROM_INIT_FILE": str(image),
        "ROM_SIZE_WORDS": rom_size_words,
    }
    if design_has_generic("RV32M_ENABLE", src_dir):
        parameters["RV32M_ENABLE"] = "true" if rv32m else "false"

    runner.test(
        hdl_toplevel="cpu",
        hdl_toplevel_lang="vhdl",
        test_module="tb_program",
        test_args=["--std=08"],
        build_dir=build_dir,
        parameters=parameters,
        extra_env=_test_env(spec_path),
        waves=waves,
    )

    metrics = json.loads(metrics_out.read_text(encoding="utf-8"))

    wave_src = build_dir / "cpu.ghw"
    wave_dst: Path | None = None
    if waves and wave_src.exists():
        wave_dst = run_dir / f"{name}.ghw"
        shutil.move(str(wave_src), wave_dst)

    return ProgramRun(
        name=name,
        metrics=metrics,
        image_path=image,
        run_dir=run_dir,
        waveform=wave_dst,
    )


def run_builtin_snapshot(
    tmp_path: Path,
    name: str,
    *,
    cycles: int,
    rv32m: bool = False,
    src_dir: Path | None = None,
    requirements: list[str] | None = None,
) -> dict:
    """Roda o programa COMPILADO NA CONSTANTE VHDL por N ciclos e devolve o estado.

    REQ: FR-RV-07 (comprovar preservação de comportamento), FR-RV-10 (o
    caminho da constante continua funcionando).

    Não informa `ROM_INIT_FILE`, ou seja, exercita exatamente o caminho
    original do design (`INSTRUCTION_MEMORY_CONTENT`).

    `src_dir` permite rodar uma árvore de fontes alternativa (por exemplo o
    RTL original extraído do git) com este mesmo harness, o que torna a
    comparação de comportamento um A/B de verdade.
    """
    run_dir = _run_dir(tmp_path, name)
    snapshot_out = run_dir / "snapshot.json"
    spec = {
        "name": name,
        "cycles": cycles,
        "requirements": requirements or [],
        "snapshot_out": str(snapshot_out),
    }
    spec_path = run_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    build_dir, runner = ensure_build(src_dir)

    parameters: dict[str, object] = {}
    if design_has_generic("RV32M_ENABLE", src_dir):
        parameters["RV32M_ENABLE"] = "true" if rv32m else "false"

    runner.test(
        hdl_toplevel="cpu",
        hdl_toplevel_lang="vhdl",
        test_module="tb_snapshot",
        test_args=["--std=08"],
        build_dir=build_dir,
        parameters=parameters,
        extra_env=_test_env(spec_path),
        waves=False,
    )

    return json.loads(snapshot_out.read_text(encoding="utf-8"))


def materialize_original_sources(dest: Path,
                                 revision: str = ORIGINAL_REVISION) -> Path:
    """Extrai do git o RTL ORIGINAL, antes das alterações desta trilha.

    REQ: FR-RV-07, NFR-RV-03 -- permite comparar o comportamento do design
    refatorado contra o original sob o mesmo testbench, em vez de confiar num
    snapshot anotado à mão.
    """
    dest.mkdir(parents=True, exist_ok=True)
    for fname in VHDL_ORDER:
        rel = f"examples/RISCV32I/src/{fname}"
        proc = subprocess.run(
            ["git", "show", f"{revision}:{rel}"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            continue          # arquivo não existia no design original
        (dest / fname).write_text(proc.stdout, encoding="utf-8")
    return dest
