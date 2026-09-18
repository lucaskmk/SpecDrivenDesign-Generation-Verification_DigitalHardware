#!/usr/bin/env python3
"""Testbench of the data RAM.

# REQ: FR-06, FR-07, FR-10

Also the acceptance test of the RAM read-out contract (FR-10): the last test
reads `dut.memory` the same way the program-level testbench of phase 4b does,
so if the array ever stops being visible through the GHDL VHPI the failure
shows up here and not as an obscure hierarchy error later.
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

RAM_BASE = 0x00FC8000
RAM_WORDS = 1024


async def start(dut):
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    dut.write_enable.value = 0
    dut.byte_enable.value = 0
    dut.addr.value = RAM_BASE
    dut.data_in.value = 0
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")


async def write_word(dut, addr: int, data: int, byte_enable: int = 0xF) -> None:
    dut.addr.value = addr
    dut.data_in.value = data
    dut.byte_enable.value = byte_enable
    dut.write_enable.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.write_enable.value = 0


async def read_word(dut, addr: int) -> int:
    dut.addr.value = addr
    await Timer(1, unit="ns")
    return int(dut.data_out.value)


@cocotb.test()
async def test_word_write_read(dut):
    """# REQ: FR-06 -- word write then asynchronous read back."""
    await start(dut)
    for offset in (0, 4, 8, 0x100, 0xFFC):
        value = (0x01010101 * (offset % 251 + 1)) & 0xFFFFFFFF
        await write_word(dut, RAM_BASE + offset, value)
        got = await read_word(dut, RAM_BASE + offset)
        assert got == value, (
            f"FR-06 violated: [0x{RAM_BASE + offset:08x}] = 0x{got:08x}, "
            f"expected 0x{value:08x}"
        )


@cocotb.test()
async def test_byte_enables(dut):
    """# REQ: FR-07 -- only the enabled byte lanes change."""
    await start(dut)
    addr = RAM_BASE + 0x20
    await write_word(dut, addr, 0x00000000)
    await write_word(dut, addr, 0xAABBCCDD, byte_enable=0b0001)
    got = await read_word(dut, addr)
    assert got == 0x000000DD, f"FR-07 violated: byte lane 0, got 0x{got:08x}"

    await write_word(dut, addr, 0x11223344, byte_enable=0b1000)
    got = await read_word(dut, addr)
    assert got == 0x110000DD, f"FR-07 violated: byte lane 3, got 0x{got:08x}"

    await write_word(dut, addr, 0x55667788, byte_enable=0b0110)
    got = await read_word(dut, addr)
    assert got == 0x116677DD, f"FR-07 violated: middle lanes, got 0x{got:08x}"


@cocotb.test()
async def test_addr_valid_flag(dut):
    """# REQ: FR-06 -- addr_valid marks the mapped 4 KB window."""
    await start(dut)
    for addr, expected in [
        (RAM_BASE, 1),
        (RAM_BASE + 0xFFC, 1),
        (RAM_BASE - 4, 0),
        (RAM_BASE + 0x1000, 0),
        (0x00000000, 0),
        (0xFFFFFFFC, 0),
    ]:
        dut.addr.value = addr
        await Timer(1, unit="ns")
        got = int(dut.addr_valid.value)
        assert got == expected, (
            f"FR-06 violated: addr_valid(0x{addr:08x}) = {got}, expected {expected}"
        )


@cocotb.test()
async def test_out_of_range_write_is_discarded(dut):
    """# REQ: FR-07 -- a write outside the window changes nothing."""
    await start(dut)
    await write_word(dut, RAM_BASE, 0x12345678)
    await write_word(dut, RAM_BASE + 0x1000, 0xFFFFFFFF)  # outside
    got = await read_word(dut, RAM_BASE)
    assert got == 0x12345678, (
        f"FR-07 violated: out-of-range write leaked, [base] = 0x{got:08x}"
    )
    # the aliased index (same low 12 bits) must not have been touched either
    dut.addr.value = RAM_BASE + 0x1000
    await Timer(1, unit="ns")
    aliased = int(dut.memory[0].value)
    assert aliased == 0x12345678, (
        f"FR-07 violated: word 0 became 0x{aliased:08x}"
    )


@cocotb.test()
async def test_memory_signal_is_readable(dut):
    """# REQ: FR-10 -- the RAM array is readable as data_ram_inst.memory."""
    await start(dut)
    random.seed(20260904)
    shadow = {}
    for _ in range(64):
        index = random.randrange(RAM_WORDS)
        value = random.getrandbits(32)
        await write_word(dut, RAM_BASE + 4 * index, value)
        shadow[index] = value

    assert len(dut.memory) == RAM_WORDS, (
        f"FR-10 violated: memory has {len(dut.memory)} words, expected {RAM_WORDS}"
    )
    for index, value in shadow.items():
        got = int(dut.memory[index].value)
        assert got == value, (
            f"FR-10 violated: memory[{index}] = 0x{got:08x}, expected 0x{value:08x}"
        )
