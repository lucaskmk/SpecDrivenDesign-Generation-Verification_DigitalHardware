#!/usr/bin/env python3
"""Testbench of the program counter.

# REQ: FR-05, FR-09
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

RESET_VECTOR = 0x00000000


@cocotb.test()
async def test_reset_loads_vector(dut):
    """# REQ: FR-09 -- synchronous, active-high reset forces the vector."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    # settle on a known state first: driving inputs in the same delta as the
    # first clock edge is a testbench race, not a DUT property.
    dut.rst.value = 1
    dut.next_pc.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    dut.rst.value = 0
    dut.next_pc.value = 0xDEADBEE0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    got = int(dut.pc.value)
    assert got == 0xDEADBEE0, (
        f"FR-05 violated: pc = 0x{got:08x}, expected 0xDEADBEE0"
    )

    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    got = int(dut.pc.value)
    assert got == RESET_VECTOR, (
        f"FR-09 violated: pc = 0x{got:08x} after reset, expected "
        f"0x{RESET_VECTOR:08x}"
    )


@cocotb.test()
async def test_reset_is_synchronous(dut):
    """# REQ: FR-09 -- reset only takes effect on a clock edge."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.next_pc.value = 0x00001000
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.pc.value) == 0x00001000

    # assert reset between edges: pc must not change until the next edge
    dut.rst.value = 1
    await Timer(1, unit="ns")
    got = int(dut.pc.value)
    assert got == 0x00001000, (
        f"FR-09 violated: reset acted asynchronously, pc = 0x{got:08x}"
    )


@cocotb.test()
async def test_loads_next_pc_every_edge(dut):
    """# REQ: FR-05 -- one PC update per rising edge, no hidden latency."""
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    random.seed(20260904)
    for _ in range(200):
        value = random.getrandbits(32) & 0xFFFFFFFC
        dut.next_pc.value = value
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
        got = int(dut.pc.value)
        assert got == value, (
            f"FR-05 violated: pc = 0x{got:08x}, expected 0x{value:08x}"
        )
