#!/usr/bin/env python3
"""Testbench of the register file.

# REQ: FR-02, FR-09
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.rst.value = 1
    dut.write_enable.value = 0
    dut.rd_addr.value = 0
    dut.rd_data.value = 0
    dut.rs1_addr.value = 0
    dut.rs2_addr.value = 0
    await RisingEdge(dut.clk)
    await RisingEdge(dut.clk)
    dut.rst.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def write(dut, addr: int, data: int) -> None:
    dut.rd_addr.value = addr
    dut.rd_data.value = data
    dut.write_enable.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.write_enable.value = 0


async def read(dut, a1: int, a2: int) -> tuple[int, int]:
    dut.rs1_addr.value = a1
    dut.rs2_addr.value = a2
    await Timer(1, unit="ns")
    return int(dut.rs1_data.value), int(dut.rs2_data.value)


@cocotb.test()
async def test_write_then_read_back(dut):
    """# REQ: FR-02 -- every writable register keeps what was written."""
    await start(dut)
    shadow = {}
    for addr in range(1, 32):
        value = (0x11111111 * addr) & 0xFFFFFFFF
        await write(dut, addr, value)
        shadow[addr] = value

    for addr in range(1, 32):
        got1, got2 = await read(dut, addr, addr)
        assert got1 == shadow[addr] and got2 == shadow[addr], (
            f"FR-02 violated: x{addr} read 0x{got1:08x}/0x{got2:08x}, "
            f"expected 0x{shadow[addr]:08x}"
        )


@cocotb.test()
async def test_x0_is_hardwired_zero(dut):
    """# REQ: FR-02 -- x0 reads zero and swallows writes."""
    await start(dut)
    await write(dut, 0, 0xDEADBEEF)
    got1, got2 = await read(dut, 0, 0)
    assert got1 == 0 and got2 == 0, (
        f"FR-02 violated: x0 must read 0, got 0x{got1:08x}/0x{got2:08x}"
    )


@cocotb.test()
async def test_two_read_ports_are_independent(dut):
    """# REQ: FR-02 -- the two read ports address different registers."""
    await start(dut)
    await write(dut, 5, 0xAAAA5555)
    await write(dut, 9, 0x5555AAAA)
    got1, got2 = await read(dut, 5, 9)
    assert (got1, got2) == (0xAAAA5555, 0x5555AAAA), (
        f"FR-02 violated: ports crossed, got 0x{got1:08x}/0x{got2:08x}"
    )


@cocotb.test()
async def test_write_enable_gates(dut):
    """# REQ: FR-02 -- with write_enable low nothing changes."""
    await start(dut)
    await write(dut, 7, 0x01234567)
    dut.rd_addr.value = 7
    dut.rd_data.value = 0xFFFFFFFF
    dut.write_enable.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    got, _ = await read(dut, 7, 0)
    assert got == 0x01234567, f"FR-02 violated: write leaked, got 0x{got:08x}"


@cocotb.test()
async def test_reset_clears(dut):
    """# REQ: FR-09 -- synchronous reset zeroes the whole bank."""
    await start(dut)
    for addr in range(1, 32):
        await write(dut, addr, 0xFFFFFFFF)
    dut.rst.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0
    for addr in range(32):
        got, _ = await read(dut, addr, 0)
        assert got == 0, f"FR-09 violated: x{addr} = 0x{got:08x} after reset"


@cocotb.test()
async def test_random_traffic(dut):
    """Random write/read mix against a Python shadow model."""
    await start(dut)
    random.seed(20260904)
    shadow = [0] * 32
    for _ in range(500):
        addr = random.randrange(0, 32)
        value = random.getrandbits(32)
        await write(dut, addr, value)
        if addr != 0:
            shadow[addr] = value
        a1, a2 = random.randrange(0, 32), random.randrange(0, 32)
        got1, got2 = await read(dut, a1, a2)
        assert got1 == shadow[a1] and got2 == shadow[a2], (
            f"FR-02 violated: x{a1}=0x{got1:08x} (exp 0x{shadow[a1]:08x}), "
            f"x{a2}=0x{got2:08x} (exp 0x{shadow[a2]:08x})"
        )
