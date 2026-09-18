#!/usr/bin/env python3
"""Testbench of the branch condition unit.

# REQ: FR-03, FR-08

Covers the classic signed/unsigned confusion (blt vs bltu around 0x80000000)
and the fact that take_branch must stay low when the instruction is not a
branch, even if the condition happens to hold.
"""
import random

import cocotb
from cocotb.triggers import Timer

FUNCT3 = {"beq": 0b000, "bne": 0b001, "blt": 0b100,
          "bge": 0b101, "bltu": 0b110, "bgeu": 0b111}


def signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


def model(name: str, a: int, b: int) -> int:
    if name == "beq":
        return int(a == b)
    if name == "bne":
        return int(a != b)
    if name == "blt":
        return int(signed(a) < signed(b))
    if name == "bge":
        return int(signed(a) >= signed(b))
    if name == "bltu":
        return int(a < b)
    if name == "bgeu":
        return int(a >= b)
    raise AssertionError(name)


EDGE_VALUES = [0x00000000, 0x00000001, 0x7FFFFFFF, 0x80000000,
               0x80000001, 0xFFFFFFFF, 0x0000FFFF]


async def check(dut, name: str, a: int, b: int) -> None:
    dut.rs1_data.value = a
    dut.rs2_data.value = b
    dut.funct3.value = FUNCT3[name]
    dut.is_branch.value = 1
    await Timer(1, unit="ns")
    got = int(dut.take_branch.value)
    expected = model(name, a, b)
    assert got == expected, (
        f"FR-03/FR-08 violated: {name} a=0x{a:08x} b=0x{b:08x} -> "
        f"got {got}, expected {expected}"
    )


@cocotb.test()
async def test_edge_values(dut):
    for name in FUNCT3:
        for a in EDGE_VALUES:
            for b in EDGE_VALUES:
                await check(dut, name, a, b)


@cocotb.test()
async def test_signed_vs_unsigned(dut):
    """# REQ: FR-03 -- blt/bge are signed, bltu/bgeu are not."""
    a, b = 0x80000000, 0x00000001  # -2^31 vs 1
    await check(dut, "blt", a, b)   # signed: -2^31 < 1  -> taken
    assert int(dut.take_branch.value) == 1
    await check(dut, "bltu", a, b)  # unsigned: huge < 1 -> not taken
    assert int(dut.take_branch.value) == 0


@cocotb.test()
async def test_not_a_branch_never_taken(dut):
    """# REQ: FR-08 -- is_branch low gates the condition entirely."""
    for name in FUNCT3:
        dut.rs1_data.value = 0
        dut.rs2_data.value = 0
        dut.funct3.value = FUNCT3[name]
        dut.is_branch.value = 0
        await Timer(1, unit="ns")
        got = int(dut.take_branch.value)
        assert got == 0, f"FR-08 violated: {name} taken with is_branch=0"


@cocotb.test()
async def test_reserved_funct3_never_taken(dut):
    """funct3 = 010/011 are not branches in RV32I (FR-14)."""
    for funct3 in (0b010, 0b011):
        dut.rs1_data.value = 0x11111111
        dut.rs2_data.value = 0x11111111
        dut.funct3.value = funct3
        dut.is_branch.value = 1
        await Timer(1, unit="ns")
        got = int(dut.take_branch.value)
        assert got == 0, f"FR-14 violated: reserved funct3={funct3:03b} taken"


@cocotb.test()
async def test_random(dut):
    random.seed(20260904)
    for _ in range(2000):
        name = random.choice(list(FUNCT3))
        await check(dut, name, random.getrandbits(32), random.getrandbits(32))
