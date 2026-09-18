#!/usr/bin/env python3
"""Comparação de eficiência RV32I contra RV32IM, benchmark a benchmark.

REQ: FR-RV-24 (ciclos, instruções, CPI, tempo estimado, stalls, flushes,
instruções RV32M), FR-RV-25 (área), NFR-RV-02 (nada é declarado como medido sem
executar a ferramenta), NFR-RV-03 (comparação sobre a mesma base de código).

Para cada benchmark de `cpus/rv32i_pipeline/programs/` existem DUAS versões do
mesmo algoritmo -- `*_rv32i.asm` (emulando multiplicação e divisão com
instruções base) e `*_rv32im.asm` (usando a extensão M). Este script executa as
duas de verdade no GHDL, via cocotb, e tabula as métricas lado a lado.

Antes de comparar QUALQUER número, o script confere que as duas versões
escreveram os MESMOS valores nos MESMOS endereços de RAM. Comparar ciclos de
dois programas que calculam coisas diferentes não significaria nada; se os
resultados divergirem, o script falha com exit code != 0 em vez de reportar.

Uso:
    python cpus/rv32i_pipeline/tools/bench_compare.py [--out DIR] [--slots N]

Requer GHDL e cocotb (na WSL). Se `ppa.json` já existir, a área medida por
`synth_ppa.py` é incorporada ao relatório.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
PROGRAMS = EXAMPLE_ROOT / "programs"

sys.path.insert(0, str(EXAMPLE_ROOT / "test"))
sys.path.insert(0, str(HERE))

from rv_build import RAM_BASE, run_program  # noqa: E402

# Quantas palavras de RAM despejar para comparar os resultados das duas versões.
DEFAULT_SLOTS = 16


def discover() -> list[tuple[str, Path, Path]]:
    """Encontra os pares (nome, .asm RV32I, .asm RV32IM)."""
    pairs = []
    for rv32i in sorted(PROGRAMS.glob("*_rv32i.asm")):
        name = rv32i.name[: -len("_rv32i.asm")]
        rv32im = PROGRAMS / f"{name}_rv32im.asm"
        if not rv32im.exists():
            print(f"aviso: {rv32i.name} nao tem par _rv32im.asm; ignorado",
                  file=sys.stderr)
            continue
        pairs.append((name, rv32i, rv32im))
    return pairs


def run_one(work: Path, label: str, asm_path: Path, *, rv32m: bool,
            slots: int, max_cycles: int) -> dict:
    """Executa um programa no GHDL e devolve métricas + despejo de RAM."""
    run = run_program(
        work,
        label,
        asm_path.read_text(encoding="utf-8"),
        max_cycles=max_cycles,
        rv32m=rv32m,
        requirements=["FR-RV-24"],
        dump_ram=(RAM_BASE, slots),
    )
    return run.metrics


def _pct(new: float, old: float) -> float | None:
    if not old:
        return None
    return round(100.0 * (new - old) / old, 2)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=None,
                    help="diretório de saída (padrão: cpus/rv32i_pipeline/ppa)")
    ap.add_argument("--slots", type=int, default=DEFAULT_SLOTS,
                    help="palavras de RAM comparadas entre as duas versões")
    ap.add_argument("--max-cycles", type=int, default=200000)
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else EXAMPLE_ROOT / "ppa"
    out_dir.mkdir(parents=True, exist_ok=True)

    pairs = discover()
    if not pairs:
        print(f"ERRO: nenhum par de benchmark encontrado em {PROGRAMS}",
              file=sys.stderr)
        return 2

    work = Path(tempfile.mkdtemp(prefix="rvbench_"))
    rows: list[dict] = []
    mismatches: list[str] = []

    try:
        for name, p_i, p_im in pairs:
            print(f"[bench] {name}: RV32I ...", flush=True)
            m_i = run_one(work, f"{name}_rv32i", p_i, rv32m=False,
                          slots=args.slots, max_cycles=args.max_cycles)
            print(f"[bench] {name}: RV32IM ...", flush=True)
            m_im = run_one(work, f"{name}_rv32im", p_im, rv32m=True,
                           slots=args.slots, max_cycles=args.max_cycles)

            # equivalência funcional antes de qualquer comparação de desempenho
            d_i = m_i.get("ram_dump", {})
            d_im = m_im.get("ram_dump", {})
            diff = {k: (d_i.get(k), d_im.get(k))
                    for k in sorted(set(d_i) | set(d_im))
                    if d_i.get(k) != d_im.get(k)}
            if diff:
                mismatches.append(
                    f"{name}: RV32I e RV32IM produziram RAM diferente -> "
                    + ", ".join(f"{k}: {a:#010x} vs {b:#010x}"
                                for k, (a, b) in diff.items())
                )

            rows.append({
                "benchmark": name,
                "ram_results": d_im,
                "results_match": not diff,
                "rv32i": m_i,
                "rv32im": m_im,
                "delta": {
                    "cycles": m_im["cycles"] - m_i["cycles"],
                    "cycles_pct": _pct(m_im["cycles"], m_i["cycles"]),
                    "instructions": m_im["instructions"] - m_i["instructions"],
                    "instructions_pct": _pct(m_im["instructions"],
                                             m_i["instructions"]),
                    "cpi": (round(m_im["cpi"] - m_i["cpi"], 4)
                            if m_im["cpi"] and m_i["cpi"] else None),
                    "stalls": m_im["stalls"] - m_i["stalls"],
                    "flushes": m_im["flushes"] - m_i["flushes"],
                    "m_instructions": m_im["m_dispatches"],
                },
            })
    finally:
        shutil.rmtree(work, ignore_errors=True)

    ppa_path = out_dir / "ppa.json"
    area = None
    if ppa_path.exists():
        area = json.loads(ppa_path.read_text(encoding="utf-8")).get("comparison")

    tot_i = sum(r["rv32i"]["cycles"] for r in rows)
    tot_im = sum(r["rv32im"]["cycles"] for r in rows)
    payload = {
        "requirements": ["FR-RV-24", "FR-RV-25", "NFR-RV-02", "NFR-RV-03"],
        "method": {
            "simulation": "GHDL 4.1.0 dirigido por cocotb 2.1.0; execucao real",
            "cycles":
                "do fim do reset ate o auto-laco de parada executar em EX "
                "(ADR-008). Ciclos de dreno do pipeline nao entram.",
            "instructions": "fetches - flush_f - (flush_d - stalls)",
            "estimated_time":
                "ESTIMATIVA: ciclos x 10 ns. O periodo realmente atingivel NAO "
                "foi medido -- exigiria biblioteca de celulas caracterizada.",
            "equivalence_check":
                "as duas versoes de cada benchmark tem de escrever os mesmos "
                "valores nos mesmos enderecos de RAM antes de qualquer "
                "comparacao de desempenho",
        },
        "benchmarks": rows,
        "totals": {
            "cycles_rv32i": tot_i,
            "cycles_rv32im": tot_im,
            "cycles_delta": tot_im - tot_i,
            "cycles_pct": _pct(tot_im, tot_i),
            "instructions_rv32i": sum(r["rv32i"]["instructions"] for r in rows),
            "instructions_rv32im": sum(r["rv32im"]["instructions"] for r in rows),
            "m_instructions_total": sum(r["rv32im"]["m_dispatches"] for r in rows),
        },
        "area": area,
        "all_results_match": not mismatches,
        "mismatches": mismatches,
    }

    json_path = out_dir / "efficiency.json"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    hdr = f"{'benchmark':<14}{'ciclos I':>9}{'ciclos IM':>10}{'Δ%':>8}" \
          f"{'instr I':>9}{'instr IM':>9}{'CPI I':>7}{'CPI IM':>8}{'M':>4}"
    print("\n" + hdr)
    print("-" * len(hdr))
    for r in rows:
        d = r["delta"]
        print(f"{r['benchmark']:<14}"
              f"{r['rv32i']['cycles']:>9}{r['rv32im']['cycles']:>10}"
              f"{d['cycles_pct']:>+8.1f}"
              f"{r['rv32i']['instructions']:>9}{r['rv32im']['instructions']:>9}"
              f"{r['rv32i']['cpi']:>7.2f}{r['rv32im']['cpi']:>8.2f}"
              f"{r['rv32im']['m_dispatches']:>4}"
              + ("" if r["results_match"] else "   <-- RESULTADO DIVERGENTE"))
    print("-" * len(hdr))
    print(f"{'TOTAL':<14}{tot_i:>9}{tot_im:>10}"
          f"{payload['totals']['cycles_pct']:>+8.1f}")
    print(f"\nescrito: {json_path}")

    if mismatches:
        print("\nERRO: equivalencia funcional falhou:", file=sys.stderr)
        for m in mismatches:
            print("  " + m, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
