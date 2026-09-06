#!/usr/bin/env python3
"""Módulo cocotb genérico: executa um programa e confere o resultado.

REQ: FR-RV-21, FR-RV-22, FR-RV-23

Este módulo é o testbench de top-level. A especificação do caso de teste
(imagem `.ram`, teto de ciclos, registradores e posições de RAM esperados)
chega por um JSON apontado pela variável de ambiente `RV_PROGRAM_SPEC`, de
modo que um único testbench serve todos os programas.

O modelo de referência (FR-RV-23) é aplicado no lado do pytest, em
`rv_build.py`; aqui só chegam os valores já calculados por ele.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb

from rv_harness import CpuHarness, CpuTimeout


def _load_spec() -> dict:
    path = os.environ.get("RV_PROGRAM_SPEC")
    if not path:
        raise RuntimeError("variável de ambiente RV_PROGRAM_SPEC não definida")
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _fmt(value: int) -> str:
    signed = value - (1 << 32) if value & 0x80000000 else value
    return f"{value:#010x} ({signed})"


@cocotb.test()
async def run_program(dut):
    """Aplica reset, executa o programa e verifica registradores e RAM."""
    spec = _load_spec()
    name = spec.get("name", "<sem nome>")
    max_cycles = int(spec.get("max_cycles", 20000))

    harness = CpuHarness(dut)

    cocotb.log.info(f"programa: {name}")
    cocotb.log.info(f"requisitos cobertos: {', '.join(spec.get('requirements', []))}")
    cocotb.log.info(f"imagem .ram: {spec.get('image')}")

    await harness.reset()

    # ---- reset deve deixar a CPU num estado sano (FR-RV-15) ----
    if spec.get("check_reset_state", True):
        assert harness.read_reg(0) == 0, "x0 deve ser zero após reset (FR-RV-04)"

    # ---- execução ----
    halt_pcs = {int(p) for p in spec.get("halt_pcs", [])}
    try:
        metrics = await harness.run_until_halt(max_cycles=max_cycles,
                                               halt_pcs=halt_pcs)
    except CpuTimeout as e:
        raise AssertionError(
            f"[{name}] TRAVAMENTO: {e}\n"
            f"Requisito afetado: FR-RV-21 (detecção de travamento)"
        ) from e

    cocotb.log.info(f"terminou em {metrics.cycles} ciclos, PC de parada "
                    f"{metrics.halt_pc:#010x}")

    # ---- verificação de registradores ----
    failures: list[str] = []

    for key, expected in sorted(spec.get("expect_regs", {}).items(), key=lambda kv: int(kv[0])):
        idx = int(key)
        got = harness.read_reg(idx)
        if got != (expected & 0xFFFFFFFF):
            failures.append(
                f"  x{idx}: esperado {_fmt(expected & 0xFFFFFFFF)}, obtido {_fmt(got)}"
            )

    # ---- verificação da RAM (FR-RV-06) ----
    for key, expected in sorted(spec.get("expect_ram", {}).items(), key=lambda kv: int(kv[0], 0)):
        addr = int(key, 0)
        got = harness.read_ram_word(addr)
        if got != (expected & 0xFFFFFFFF):
            failures.append(
                f"  RAM[{addr:#010x}]: esperado {_fmt(expected & 0xFFFFFFFF)}, "
                f"obtido {_fmt(got)}"
            )

    # ---- x0 permanentemente zero (FR-RV-04) ----
    if harness.read_reg(0) != 0:
        failures.append("  x0 deixou de ser zero (FR-RV-04)")

    # ---- métricas para o relatório de eficiência (FR-RV-24) ----
    out = spec.get("metrics_out")
    if out:
        payload = metrics.as_dict()
        payload["name"] = name
        payload["rv32m_enable"] = spec.get("rv32m_enable")
        Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        cocotb.log.info(f"métricas gravadas em {out}")

    if failures:
        reqs = ", ".join(spec.get("requirements", [])) or "FR-RV-22"
        raise AssertionError(
            f"[{name}] {len(failures)} verificação(ões) falharam "
            f"(requisito(s): {reqs}):\n" + "\n".join(failures)
            + f"\nMétricas: {metrics.as_dict()}"
        )

    cocotb.log.info(f"[{name}] OK — {metrics.instructions} instruções, "
                    f"CPI {metrics.cpi:.3f}, {metrics.stalls} stalls, "
                    f"{metrics.flushes} flushes")
