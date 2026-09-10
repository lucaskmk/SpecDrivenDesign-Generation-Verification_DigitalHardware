#!/usr/bin/env python3
"""Modulo cocotb GENERICO: roda um programa em qualquer CPU com `cpu.toml`.

REQ: FR-RV-21, FR-RV-22, FR-RV-23, NFR-RV-02.

Este e o testbench de top-level do validador. Ele nao conhece nenhuma CPU:
tudo o que sabe sobre o design vem do manifesto, e tudo o que sabe sobre o
caso de teste vem de um JSON apontado por `RVVERIFY_SPEC`:

    {
      "manifest":   "caminho/para/cpu.toml",
      "name":       "nome do caso",
      "max_cycles": 20000,
      "halt_pcs":   [104],
      "expect_regs": {"5": 42},          # opcional
      "expect_ram":  {"0xfc8100": 42},   # opcional
      "dump_ram":    {"start": 16549632, "count": 4},   # opcional
      "report_out":  "caminho/report.json"              # opcional
    }

O modelo de referencia (FR-RV-23) roda do lado do pytest; aqui so chegam os
valores ja calculados por ele.

DEGRADACAO GRACIOSA: o relatorio traz `observability` e `unobserved`, dizendo
o que este manifesto permitiu verificar e o que nao permitiu. Se o caso de
teste pedir uma verificacao que o manifesto nao suporta (por exemplo esperar
um valor de registrador sem `[observe].registers`), o teste FALHA com essa
explicacao -- passar em silencio seria mentir sobre a cobertura.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb

from rvverify.harness import CpuHarness, CpuTimeout
from rvverify.manifest import load_manifest


def _load_spec() -> dict:
    path = os.environ.get("RVVERIFY_SPEC")
    if not path:
        raise RuntimeError("variavel de ambiente RVVERIFY_SPEC nao definida")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt(value: int) -> str:
    signed = value - (1 << 32) if value & 0x80000000 else value
    return f"{value:#010x} ({signed})"


@cocotb.test()
async def run_program(dut):
    """Aplica reset, executa o programa e verifica o que o manifesto permite."""
    spec = _load_spec()
    name = spec.get("name", "<sem nome>")
    manifest = load_manifest(spec["manifest"])
    max_cycles = int(spec.get("max_cycles", 20000))

    harness = CpuHarness(dut, manifest)
    caps = harness.capabilities

    cocotb.log.info(f"CPU: {manifest.design.name} (top {manifest.design.top})")
    cocotb.log.info(f"programa: {name}")
    cocotb.log.info(f"requisitos cobertos: {', '.join(spec.get('requirements', []))}")
    cocotb.log.info(f"modo de parada: {manifest.halt.mode}")
    for item in caps["unobserved"]:
        cocotb.log.warning(f"NAO OBSERVAVEL -- {item}")

    await harness.reset()

    expect_regs = spec.get("expect_regs", {})
    expect_ram = spec.get("expect_ram", {})

    # Pedir verificacao que o manifesto nao suporta e erro, nao "ok".
    if expect_regs and not caps["registers"]:
        raise AssertionError(
            f"[{name}] o caso de teste espera valores de registrador, mas "
            f"{manifest.path} nao declara [observe].registers. Sem esse caminho "
            f"o validador so consegue verificar RAM e ciclos (NFR-RV-02)."
        )

    if caps["registers"] and spec.get("check_reset_state", True):
        assert harness.read_reg(0) == 0, "x0 deve ser zero apos reset (FR-RV-04)"

    # ---- execucao ----
    halt_pcs = {int(p) for p in spec.get("halt_pcs", [])}
    try:
        metrics = await harness.run_until_halt(max_cycles=max_cycles,
                                               halt_pcs=halt_pcs)
    except CpuTimeout as e:
        raise AssertionError(
            f"[{name}] TRAVAMENTO: {e}\n"
            f"Requisito afetado: FR-RV-21 (deteccao de travamento)"
        ) from e

    halt_txt = "n/d" if metrics.halt_pc is None else f"{metrics.halt_pc:#010x}"
    cocotb.log.info(f"terminou em {metrics.cycles} ciclos, PC de parada {halt_txt}")

    # ---- verificacoes ----
    failures: list[str] = []

    for key, expected in sorted(expect_regs.items(), key=lambda kv: int(kv[0])):
        idx = int(key)
        got = harness.read_reg(idx)
        if got != (expected & 0xFFFFFFFF):
            failures.append(
                f"  x{idx}: esperado {_fmt(expected & 0xFFFFFFFF)}, "
                f"obtido {_fmt(got)}"
            )

    for key, expected in sorted(expect_ram.items(), key=lambda kv: int(kv[0], 0)):
        addr = int(key, 0)
        got = harness.read_ram_word(addr)
        if got != (expected & 0xFFFFFFFF):
            failures.append(
                f"  RAM[{addr:#010x}]: esperado {_fmt(expected & 0xFFFFFFFF)}, "
                f"obtido {_fmt(got)}"
            )

    if caps["registers"] and harness.read_reg(0) != 0:
        failures.append("  x0 deixou de ser zero (FR-RV-04)")

    # ---- relatorio ----
    out = spec.get("report_out") or spec.get("metrics_out")
    if out:
        payload = metrics.as_dict()
        payload["name"] = name
        payload["design"] = manifest.design.name
        payload["halt_mode"] = manifest.halt.mode
        payload["observability"] = caps
        payload["registers"] = (harness.read_all_regs()
                                if caps["registers"] else None)
        dump = spec.get("dump_ram")
        if dump:
            start = int(dump["start"], 0) if isinstance(dump["start"], str) \
                else int(dump["start"])
            payload["ram_dump"] = {
                hex(start + 4 * i): harness.read_ram_word(start + 4 * i)
                for i in range(int(dump["count"]))
            }
        Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        cocotb.log.info(f"relatorio gravado em {out}")

    if failures:
        reqs = ", ".join(spec.get("requirements", [])) or "FR-RV-22"
        raise AssertionError(
            f"[{name}] {len(failures)} verificacao(oes) falharam "
            f"(requisito(s): {reqs}):\n" + "\n".join(failures)
            + f"\nMetricas: {metrics.as_dict()}"
        )

    n = metrics.instructions
    resumo = (f"{n} instrucoes, CPI {metrics.cpi:.3f}" if n
              else "instrucoes/CPI nao observaveis neste manifesto")
    cocotb.log.info(f"[{name}] OK -- {metrics.cycles} ciclos, {resumo}")
