#!/usr/bin/env python3
"""Testbench of the integer ALU.

# REQ: FR-03, FR-12

The expected values come from an independent Python model of the RISC-V
integer operations, not from the VHDL: the point is to catch a wrong
encoding or a wrong shift width, which a model derived from the DUT would
never see.
"""
import random

import cocotb
from cocotb.triggers import Timer

MASK32 = 0xFFFFFFFF

# encoding of cpu_pkg.vhd
ALU_ADD, ALU_SUB, ALU_AND, ALU_OR, ALU_XOR = 0, 1, 2, 3, 4
ALU_SLL, ALU_SRL, ALU_SRA, ALU_SLT, ALU_SLTU, ALU_PASS_B = 5, 6, 7, 8, 9, 10

OPS = {
    ALU_ADD: "add", ALU_SUB: "sub", ALU_AND: "and", ALU_OR: "or",
    ALU_XOR: "xor", ALU_SLL: "sll", ALU_SRL: "srl", ALU_SRA: "sra",
    ALU_SLT: "slt", ALU_SLTU: "sltu", ALU_PASS_B: "pass_b",
}

EDGE_VALUES = [
    0x00000000, 0x00000001, 0x00000002, 0x7FFFFFFF, 0x80000000,
    0xFFFFFFFF, 0xFFFFFFFE, 0x0000001F, 0x00000020, 0xDEADBEEF, 0x0000FFFF,
]


def signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


def model(op: int, a: int, b: int) -> int:
    """Independent reference model (RISC-V unprivileged spec)."""
    shamt = b & 0x1F  # REQ: FR-12 -- only the low 5 bits count
    if op == ALU_ADD:
        return (a + b) & MASK32
    if op == ALU_SUB:
        return (a - b) & MASK32
    if op == ALU_AND:
        return a & b
    if op == ALU_OR:
        return a | b
    if op == ALU_XOR:
        return a ^ b
    if op == ALU_SLL:
        return (a << shamt) & MASK32
    if op == ALU_SRL:
        return (a % (1 << 32)) >> shamt
    if op == ALU_SRA:
        return (signed(a) >> shamt) & MASK32
    if op == ALU_SLT:
        return 1 if signed(a) < signed(b) else 0
    if op == ALU_SLTU:
        return 1 if a < b else 0
    if op == ALU_PASS_B:
        return b
    raise AssertionError(f"unknown op {op}")


async def check(dut, op: int, a: int, b: int) -> None:
    dut.a.value = a
    dut.b.value = b
    dut.alu_op.value = op
    await Timer(1, unit="ns")
    got = int(dut.result.value)
    expected = model(op, a, b)
    assert got == expected, (
        f"FR-03/FR-12 violated: {OPS[op]} a=0x{a:08x} b=0x{b:08x} -> "
        f"got 0x{got:08x}, expected 0x{expected:08x}"
    )


@cocotb.test()
async def test_edge_values(dut):
    """Every operation against the interesting corners of the 32-bit range."""
    for op in OPS:
        for a in EDGE_VALUES:
            for b in EDGE_VALUES:
                await check(dut, op, a, b)


@cocotb.test()
async def test_random(dut):
    """Random stimulus over the whole operation set."""
    random.seed(20260904)
    for _ in range(2000):
        op = random.choice(list(OPS))
        await check(dut, op, random.getrandbits(32), random.getrandbits(32))


@cocotb.test()
async def test_shift_amount_is_five_bits(dut):
    """# REQ: FR-12 -- shift amount ignores b[31:5]."""
    for shamt in range(32):
        for high_noise in (0x00000000, 0xFFFFFFE0, 0x000000A0):
            b = high_noise | shamt
            for op in (ALU_SLL, ALU_SRL, ALU_SRA):
                await check(dut, op, 0xDEADBEEF, b)


@cocotb.test()
async def test_unknown_opcode_is_zero(dut):
    """Unused ALU codes must be inert, not alias onto a real operation."""
    for op in (11, 12, 13, 14, 15):
        dut.a.value = 0x12345678
        dut.b.value = 0x9ABCDEF0
        dut.alu_op.value = op
        await Timer(1, unit="ns")
        got = int(dut.result.value)
        assert got == 0, f"alu_op={op} should be inert, got 0x{got:08x}"
