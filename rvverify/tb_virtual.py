"""Testbench cocotb com ROM e RAM virtuais para a entidade ``cpu``."""
from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer

MASK32 = 0xFFFFFFFF
RAM_BASE = 0x00FC8100
RAM_BYTES = 512


def _spec() -> dict:
    return json.loads(Path(os.environ["RVVERIFY_SPEC"]).read_text(encoding="utf-8"))


def _write(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


@cocotb.test()
async def run_program(dut):
    spec = _spec()
    words = [int(x) & MASK32 for x in spec["program_words"]]
    ram: dict[int, int] = {}
    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())
    dut.rst.value = 1
    dut.instr_data.value = words[0] if words else 0
    dut.data_read_data.value = 0
    await Timer(1, unit="ns")
    for _ in range(3):
        await RisingEdge(dut.clk)
    dut.rst.value = 0

    halt = {int(x) for x in spec.get("halt_pcs", [])}
    stable_halt = 0
    cycles = 0
    try:
        for cycles in range(1, int(spec.get("max_cycles", 20000)) + 1):
            await FallingEdge(dut.clk)
            iaddr = int(dut.instr_addr.value)
            index = iaddr // 4
            dut.instr_data.value = words[index] if 0 <= index < len(words) else 0
            daddr = int(dut.data_addr.value)
            aligned = daddr & ~3
            dut.data_read_data.value = ram.get(aligned, 0)
            await RisingEdge(dut.clk)
            if int(dut.data_write.value):
                width = int(dut.data_width.value)
                old, value = ram.get(aligned, 0), int(dut.data_write_data.value) & MASK32
                shift = (daddr & 3) * 8
                if width == 0:
                    mask, value = 0xFF << shift, (value & 0xFF) << shift
                elif width == 1:
                    mask, value = 0xFFFF << ((daddr & 2) * 8), (value & 0xFFFF) << ((daddr & 2) * 8)
                else:
                    mask = MASK32
                if RAM_BASE <= aligned < RAM_BASE + RAM_BYTES:
                    ram[aligned] = ((old & ~mask) | value) & MASK32
            stable_halt = stable_halt + 1 if iaddr in halt else 0
            if stable_halt >= 3:
                break
        else:
            raise AssertionError("CPU did not reach the halt loop")

        falhas = []
        for addr, esperado in spec.get("expect_ram", {}).items():
            a, e = int(addr, 0), int(esperado) & MASK32
            obtido = ram.get(a & ~3, 0)
            if obtido != e:
                falhas.append({"address": hex(a), "expected": e, "actual": obtido})
        payload = {"resultado": "passou" if not falhas else "falhou", "falhas": falhas,
                   "erro": None, "cycles": cycles, "ram_dump": {hex(k): v for k, v in ram.items()}}
        _write(spec["report_out"], payload)
        assert not falhas, f"RAM mismatches: {falhas}"
    except BaseException as e:
        _write(spec["report_out"], {"resultado": "falhou", "falhas": [], "erro": str(e), "cycles": cycles})
        raise
