#!/usr/bin/env python3
"""Testbench of the load/store unit.

# REQ: FR-06, FR-07

Three things get checked here, and each of them is a classic silent bug:
  * byte/halfword lane selection in little-endian order,
  * sign extension (lb/lh) vs zero extension (lbu/lhu),
  * the FR-07 rule for a misaligned or out-of-range access -- read 0xFFFFFFFF
    and discard the write, with no exception.
"""
import random

import cocotb
from cocotb.triggers import Timer

MASK32 = 0xFFFFFFFF
INVALID_READ = 0xFFFFFFFF

LB, LH, LW, LBU, LHU = 0b000, 0b001, 0b010, 0b100, 0b101
SB, SH, SW = 0b000, 0b001, 0b010

LOAD_NAMES = {LB: "lb", LH: "lh", LW: "lw", LBU: "lbu", LHU: "lhu"}


def sign_extend(value: int, width: int) -> int:
    if value & (1 << (width - 1)):
        value -= 1 << width
    return value & MASK32


def load_model(funct3: int, word: int, addr_low: int) -> int:
    """Reference model of a load from a word already fetched from memory."""
    if funct3 in (LH, LHU) and (addr_low & 1):
        return INVALID_READ
    if funct3 == LW and (addr_low & 3):
        return INVALID_READ
    if funct3 in (LB, LBU):
        byte = (word >> (8 * addr_low)) & 0xFF
        return sign_extend(byte, 8) if funct3 == LB else byte
    if funct3 in (LH, LHU):
        half = (word >> (16 * (addr_low >> 1))) & 0xFFFF
        return sign_extend(half, 16) if funct3 == LH else half
    return word


def store_model(funct3: int, data: int, addr_low: int) -> tuple[int, int]:
    """Reference model of byte enables and lane-aligned store data."""
    if funct3 == SB:
        return 1 << addr_low, (data & 0xFF) << (8 * addr_low)
    if funct3 == SH:
        half_index = addr_low >> 1
        return 0b11 << (2 * half_index), (data & 0xFFFF) << (16 * half_index)
    return 0b1111, data & MASK32


async def drive_load(dut, funct3: int, word: int, addr: int,
                     ram_valid: int = 1, rom_valid: int = 0) -> int:
    dut.addr.value = addr
    dut.funct3.value = funct3
    dut.mem_write.value = 0
    dut.store_data.value = 0
    dut.ram_data.value = word if ram_valid else 0
    dut.rom_data.value = word if rom_valid else 0
    dut.ram_valid.value = ram_valid
    dut.rom_valid.value = rom_valid
    await Timer(1, unit="ns")
    return int(dut.load_result.value)


@cocotb.test()
async def test_loads_from_ram(dut):
    """# REQ: FR-07 -- every load width and offset, sign and zero extended."""
    random.seed(20260904)
    words = [0x00000000, 0xFFFFFFFF, 0x807F0180, 0x12345678, 0xDEADBEEF]
    words += [random.getrandbits(32) for _ in range(40)]
    for word in words:
        for funct3 in LOAD_NAMES:
            for addr_low in range(4):
                addr = 0x00FC8000 + addr_low
                got = await drive_load(dut, funct3, word, addr)
                expected = load_model(funct3, word, addr_low)
                assert got == expected, (
                    f"FR-07 violated: {LOAD_NAMES[funct3]} word=0x{word:08x} "
                    f"offset={addr_low} -> got 0x{got:08x}, "
                    f"expected 0x{expected:08x}"
                )


@cocotb.test()
async def test_loads_from_rom(dut):
    """# REQ: FR-06 -- .rodata loads take the ROM port."""
    word = 0xCAFEBABE
    got = await drive_load(dut, LW, word, 0x00000010, ram_valid=0, rom_valid=1)
    assert got == word, f"FR-06 violated: ROM load gave 0x{got:08x}"
    got = await drive_load(dut, LBU, word, 0x00000012, ram_valid=0, rom_valid=1)
    assert got == 0xFE, f"FR-06 violated: ROM lbu gave 0x{got:08x}"


@cocotb.test()
async def test_out_of_range_load(dut):
    """# REQ: FR-07 -- neither region valid -> 0xFFFFFFFF."""
    got = await drive_load(dut, LW, 0x12345678, 0x40000000,
                           ram_valid=0, rom_valid=0)
    assert got == INVALID_READ, (
        f"FR-07 violated: out-of-range load gave 0x{got:08x}"
    )


@cocotb.test()
async def test_misaligned_load(dut):
    """# REQ: FR-07 -- misaligned lw/lh read 0xFFFFFFFF."""
    for funct3, addr_low in [(LW, 1), (LW, 2), (LW, 3), (LH, 1), (LHU, 3)]:
        got = await drive_load(dut, funct3, 0x12345678, 0x00FC8000 + addr_low)
        assert got == INVALID_READ, (
            f"FR-07 violated: misaligned {LOAD_NAMES[funct3]} at offset "
            f"{addr_low} gave 0x{got:08x}"
        )


@cocotb.test()
async def test_stores(dut):
    """# REQ: FR-07 -- byte enables and lane placement for sb/sh/sw."""
    random.seed(1)
    for data in [0x000000AB, 0x0000CDEF, 0x89ABCDEF] + [random.getrandbits(32) for _ in range(20)]:
        for funct3 in (SB, SH, SW):
            for addr_low in range(4):
                if funct3 == SH and addr_low & 1:
                    continue
                if funct3 == SW and addr_low:
                    continue
                addr = 0x00FC8004 + addr_low
                dut.addr.value = addr
                dut.funct3.value = funct3
                dut.store_data.value = data
                dut.mem_write.value = 1
                dut.ram_valid.value = 1
                dut.rom_valid.value = 0
                dut.ram_data.value = 0
                dut.rom_data.value = 0
                await Timer(1, unit="ns")
                be_expected, dw_expected = store_model(funct3, data, addr_low)
                be_got = int(dut.ram_byte_enable.value)
                dw_got = int(dut.ram_data_in.value)
                we_got = int(dut.ram_write_enable.value)
                assert we_got == 1, (
                    f"FR-07 violated: aligned store not enabled "
                    f"(funct3={funct3:03b}, offset={addr_low})"
                )
                assert be_got == be_expected, (
                    f"FR-07 violated: byte_enable = {be_got:04b}, "
                    f"expected {be_expected:04b} (funct3={funct3:03b}, "
                    f"offset={addr_low})"
                )
                # only the enabled lanes need to match
                for lane in range(4):
                    if be_expected & (1 << lane):
                        got_lane = (dw_got >> (8 * lane)) & 0xFF
                        exp_lane = (dw_expected >> (8 * lane)) & 0xFF
                        assert got_lane == exp_lane, (
                            f"FR-07 violated: lane {lane} = 0x{got_lane:02x}, "
                            f"expected 0x{exp_lane:02x}"
                        )


@cocotb.test()
async def test_store_outside_ram_is_blocked(dut):
    """# REQ: FR-07 -- write enable stays low outside the RAM window."""
    for ram_valid, rom_valid, label in [(0, 1, "ROM range"), (0, 0, "unmapped")]:
        dut.addr.value = 0x00000010
        dut.funct3.value = SW
        dut.store_data.value = 0xFFFFFFFF
        dut.mem_write.value = 1
        dut.ram_valid.value = ram_valid
        dut.rom_valid.value = rom_valid
        await Timer(1, unit="ns")
        got = int(dut.ram_write_enable.value)
        assert got == 0, f"FR-07 violated: store into {label} was enabled"


@cocotb.test()
async def test_misaligned_store_is_blocked(dut):
    """# REQ: FR-07 -- misaligned store is discarded, not truncated."""
    for funct3, addr_low in [(SW, 1), (SW, 2), (SW, 3), (SH, 1), (SH, 3)]:
        dut.addr.value = 0x00FC8000 + addr_low
        dut.funct3.value = funct3
        dut.store_data.value = 0xFFFFFFFF
        dut.mem_write.value = 1
        dut.ram_valid.value = 1
        dut.rom_valid.value = 0
        await Timer(1, unit="ns")
        got = int(dut.ram_write_enable.value)
        assert got == 0, (
            f"FR-07 violated: misaligned store (funct3={funct3:03b}, "
            f"offset={addr_low}) was enabled"
        )
