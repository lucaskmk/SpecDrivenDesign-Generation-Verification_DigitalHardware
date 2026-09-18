#!/usr/bin/env python3
"""Fase 5 -- monta ppa/ppa.json a partir dos logs REAIS do Yosys.

REQ: FR-15 (A/B da extensao), NFR-01 (area), NFR-02 (caminho critico)
REQ (repositorio): repo:FR-RV-25, ADR-005
Constituicao, principio 10: todo numero aqui saiu de uma execucao de
ferramenta cujo log esta versionado ao lado. Nada e estimado sem rotulo.

Uso:  python3 ppa/build_ppa.py        (a partir da raiz da CPU)
"""
import json, re, pathlib

PPA = pathlib.Path(__file__).resolve().parent
norm = lambda n: re.sub(r"_[0-9a-f]{40}$", "", n)
STORAGE = ("data_ram", "instruction_rom", "register_file")


def sections(path):
    """{modulo: {metrica: valor}} de um log de `yosys stat`."""
    blocks, hier, cur = {}, {}, None
    for line in path.read_text(errors="replace").splitlines():
        m = re.match(r"^=== (.+?) ===$", line.strip())
        if m:
            cur = m.group(1)
            continue
        if cur is None:
            continue
        m = re.match(r"\s+Number of (cells|wires|wire bits|memory bits):\s+(\d+)", line)
        if m:
            key, val = m.group(1).replace(" ", "_"), int(m.group(2))
            (hier if cur == "design hierarchy" else blocks.setdefault(norm(cur), {}))[key] = val
            continue
        m = re.match(r"\s+(\$[\w]+)\s+(\d+)", line)
        if m:
            tgt = hier if cur == "design hierarchy" else blocks.setdefault(norm(cur), {})
            tgt.setdefault("cell_types", {})[m.group(1)] = int(m.group(2))
    return blocks, hier


def ltp(path):
    if not path.exists():
        return {}
    return {norm(m.group(1)): int(m.group(2)) for m in re.finditer(
        r"Longest topological path in (\S+) \(length=(\d+)\)", path.read_text(errors="replace"))}


def config(cfg):
    stat = PPA / f"yosys_stat_{cfg}.log"
    if not stat.exists():
        return None
    blocks, hier = sections(stat)
    depth = ltp(PPA / f"yosys_ltp_{cfg}.log")
    ff = sum(v for k, v in hier.get("cell_types", {}).items() if "DFF" in k)
    latch = sum(v for k, v in hier.get("cell_types", {}).items() if "DLATCH" in k)
    out = {
        "config": cfg,
        "rv32m_enable": cfg == "rv32im",
        "generic_cells_total": hier.get("cells"),
        "generic_cells_by_block": {b: v.get("cells") for b, v in sorted(blocks.items())},
        "flip_flops": ff,
        "latches": latch,
        "memory_macros": hier.get("cell_types", {}).get("$mem_v2"),
        "memory_bits_expanded": hier.get("memory_bits"),
        "logic_depth_levels": depth,
        "verilog_lines": len((PPA / f"cpu_{cfg}.v").read_text(errors="replace").splitlines())
                         if (PPA / f"cpu_{cfg}.v").exists() else None,
        "measured_by": "ghdl synth --out=verilog + yosys stat (medicao real, ADR-005)",
    }
    lut_log = PPA / f"yosys_lut4_{cfg}.log"
    if lut_log.exists():
        lb, lh = sections(lut_log)
        luts = lh.get("cell_types", {}).get("$lut")
        if luts is not None:
            out["lut4"] = {
                "total": luts,
                "by_block": {b: v.get("cell_types", {}).get("$lut") for b, v in sorted(lb.items())},
                "flip_flops": sum(v for k, v in lh.get("cell_types", {}).items() if "DFF" in k),
                "latches": sum(v for k, v in lh.get("cell_types", {}).items() if "DLATCH" in k),
                "memory_macros": lh.get("cell_types", {}).get("$mem_v2"),
                "measured_by": "yosys abc -lut 4 (medicao real); memorias mantidas "
                               "como macro $mem_v2, logo o numero e de LOGICA de nucleo",
            }
        else:
            out["lut4"] = {"total": None, "status": "mapeamento nao concluido; log presente mas sem $lut"}
    else:
        out["lut4"] = {"total": None, "status": "NAO EXECUTADO"}
    return out


configs = {c: config(c) for c in ("rv32i", "rv32im")}
configs = {k: v for k, v in configs.items() if v}

report = {
    "design": "rv32im_sc",
    "phase": "5 (analise PPA)",
    "requirements": ["FR-15", "NFR-01", "NFR-02", "NFR-03", "repo:FR-RV-25"],
    "method": {
        "synthesis": "ghdl synth --std=08 -gRV32M_ENABLE=<cfg> --out=verilog cpu",
        "stat": "read_verilog cpu_<cfg>.v; hierarchy -top cpu; proc; memory -nomap; "
                "opt_expr; techmap; stat",
        "ltp": "... ; ltp -noff  (caminho topologico mais longo, em NIVEIS DE LOGICA)",
        "lut4": "... ; opt -fast; techmap; opt -fast; abc -lut 4; opt -fast; stat",
        "adr": "ADR-005 -- ghdl-yosys-plugin nao esta instalado; o caminho e "
               "`ghdl synth --out=verilog` alimentando o Yosys",
        "hierarchy_kept": "o design NAO e achatado: as contagens por bloco sao o "
                          "que permite atribuir a area a extensao M",
        "cell_meaning": "celulas genericas do Yosys apos techmap; comparaveis entre as "
                        "duas configuracoes, NAO equivalentes a um PDK nem a LUTs",
        "lut_meaning": "$lut apos `abc -lut 4` e contagem real de LUT4 de logica de "
                       "nucleo; ROM e RAM ficam como macro $mem_v2 e por isso nao entram",
        "lut_meaning_ressalva": "CORRIGIDO NA FASE 5b: a frase original dizia que o macro "
                       "$mem_v2 vira 'block RAM num FPGA'. O Quartus mediu o contrario -- "
                       "0 de 3.153.920 bits de block memory usados, e a data_ram virou "
                       "32.768 flip-flops mais um mux 1024:1 de 17.050 LEs. Leitura "
                       "ASSINCRONA nao infere M10K. Logo o total de LUT4 aqui SUBESTIMA "
                       "a area de FPGA: ver fpga/ e RELATORIO.md, fase 5b",
        "depth_meaning": "NIVEIS DE LOGICA, nao nanossegundos. Nenhuma ferramenta DESTA "
                         "imagem faz analise temporal com biblioteca de celulas",
        "timing_medido_na_fase_5b": "Fmax foi medido depois, pelo TimeQuest do Quartus "
                         "(fpga/, repo:FR-RV-38): 9,84 MHz contra alvo de 50 MHz, slack "
                         "de setup -84,977 ns. Ver fpga/quartus_output_rv32im_a9/",
        "power": "NAO MEDIDO NESTA FASE: nao ha ferramenta de potencia nesta imagem. "
                 "Estimado na fase 5b pelo Power Analyzer do Quartus (repo:FR-RV-39): "
                 "3.623,2 mW contra orcamento de 500 mW, confianca BAIXA por falta de "
                 "toggle rate. Ver fpga/quartus_output_rv32im_a9/reports/power.json",
    },
    "configs": configs,
}

if "rv32i" in configs and "rv32im" in configs:
    a, b = configs["rv32i"], configs["rv32im"]
    per_block = {}
    for blk in sorted(set(a["generic_cells_by_block"]) | set(b["generic_cells_by_block"])):
        ca = a["generic_cells_by_block"].get(blk, 0) or 0
        cb = b["generic_cells_by_block"].get(blk, 0) or 0
        per_block[blk] = {"rv32i": ca, "rv32im": cb, "delta": cb - ca}
    report["comparison"] = {
        "generic_cells_rv32i": a["generic_cells_total"],
        "generic_cells_rv32im": b["generic_cells_total"],
        "delta_cells": b["generic_cells_total"] - a["generic_cells_total"],
        "ratio": round(b["generic_cells_total"] / a["generic_cells_total"], 4),
        "per_block": per_block,
        "mul_div_share_of_rv32im": round(
            100.0 * (b["generic_cells_by_block"].get("mul_div_unit") or 0)
            / b["generic_cells_total"], 2),
        "logic_depth_top": {"rv32i": a["logic_depth_levels"].get("cpu"),
                            "rv32im": b["logic_depth_levels"].get("cpu")},
        "flip_flops": {"rv32i": a["flip_flops"], "rv32im": b["flip_flops"],
                       "note": "identicos: a extensao M e puramente combinacional neste design"},
    }
    if a.get("lut4", {}).get("total") and b.get("lut4", {}).get("total"):
        report["comparison"]["lut4"] = {
            "rv32i": a["lut4"]["total"], "rv32im": b["lut4"]["total"],
            "delta": b["lut4"]["total"] - a["lut4"]["total"],
            "ratio": round(b["lut4"]["total"] / a["lut4"]["total"], 4)}

(PPA / "ppa.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({k: v for k, v in report.get("comparison", {}).items()
                  if k != "per_block"}, indent=2))
for c, v in configs.items():
    print(f"{c:<7} generic={v['generic_cells_total']:>8}  lut4={v['lut4'].get('total')}  "
          f"ff={v['flip_flops']}  latches={v['latches']}  depth(cpu)={v['logic_depth_levels'].get('cpu')}")
