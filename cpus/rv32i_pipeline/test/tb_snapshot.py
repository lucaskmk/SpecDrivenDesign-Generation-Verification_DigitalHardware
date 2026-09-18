#!/usr/bin/env python3
"""Módulo cocotb: roda N ciclos e fotografa o estado da CPU.

REQ: FR-RV-07 (prova de preservação de comportamento após a refatoração das
memórias), FR-RV-10 (o caminho da constante VHDL continua válido).

Usado para comparar o estado da CPU rodando o programa original contra o
snapshot capturado ANTES da refatoração (ver specs/decisions.md, ADR-000,
execução 4).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb

from rv_harness import CpuHarness


@cocotb.test()
async def snapshot(dut):
    spec = json.loads(Path(os.environ["RV_PROGRAM_SPEC"]).read_text(encoding="utf-8"))
    cycles = int(spec["cycles"])

    harness = CpuHarness(dut)
    await harness.reset()
    metrics = await harness.run_cycles(cycles)

    payload = {
        "name": spec.get("name"),
        "cycles_run": cycles,
        "pc": harness.pc,
        "registers": harness.read_all_regs(),
        "metrics": metrics.as_dict(),
    }

    out = spec.get("snapshot_out")
    if out:
        Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    cocotb.log.info(f"PC = {harness.pc:#010x}")
    for i, v in enumerate(payload["registers"]):
        if v:
            cocotb.log.info(f"  x{i} = {v:#010x}")
