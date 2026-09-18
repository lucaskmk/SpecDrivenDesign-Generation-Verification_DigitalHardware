#!/usr/bin/env python3
"""Testbench of the M extension unit.

# REQ: FR-04, FR-11

The reference model is written from the RISC-V unprivileged specification
(truncation toward zero, remainder with the sign of the dividend, and the two
special cases: division by zero and the -2^31 / -1 overflow). Python's own
`//` and `%` floor instead of truncating, so the model implements the RISC-V
rule explicitly -- copying Python semantics here would have hidden a real
bug class.
"""
import random

import cocotb
from cocotb.triggers import Timer

MASK32 = 0xFFFFFFFF
MASK64 = 0xFFFFFFFFFFFFFFFF

MD_MUL, MD_MULH, MD_MULHSU, MD_MULHU = 0, 1, 2, 3
MD_DIV, MD_DIVU, MD_REM, MD_REMU = 4, 5, 6, 7

NAMES = {
    MD_MUL: "mul", MD_MULH: "mulh", MD_MULHSU: "mulhsu", MD_MULHU: "mulhu",
    MD_DIV: "div", MD_DIVU: "divu", MD_REM: "rem", MD_REMU: "remu",
}

EDGE_VALUES = [
    0x00000000, 0x00000001, 0x00000002, 0x00000003, 0x0000000A,
    0x7FFFFFFF, 0x80000000, 0x80000001, 0xFFFFFFFF, 0xFFFFFFFE,
    0x0000FFFF, 0xFFFF0000, 0x12345678, 0xDEADBEEF,
]


def signed(value: int) -> int:
    return value - (1 << 32) if value & 0x80000000 else value


def trunc_div(n: int, d: int) -> int:
    """Integer division truncated toward zero (C / RISC-V semantics)."""
    q = abs(n) // abs(d)
    return -q if (n < 0) != (d < 0) else q


def trunc_rem(n: int, d: int) -> int:
    """Remainder with the sign of the dividend (C / RISC-V semantics)."""
    return n - trunc_div(n, d) * d


def model(op: int, a: int, b: int) -> int:
    sa, sb = signed(a), signed(b)
    if op == MD_MUL:
        return (a * b) & MASK32
    if op == MD_MULH:
        return ((sa * sb) >> 32) & MASK32
    if op == MD_MULHSU:
        return ((sa * b) >> 32) & MASK32
    if op == MD_MULHU:
        return ((a * b) >> 32) & MASK32
    # REQ: FR-11 -- edge semantics
    if op == MD_DIV:
        if b == 0:
            return MASK32
        if a == 0x80000000 and b == MASK32:
            return 0x80000000
        return trunc_div(sa, sb) & MASK32
    if op == MD_DIVU:
        return MASK32 if b == 0 else (a // b) & MASK32
    if op == MD_REM:
        if b == 0:
            return a
        if a == 0x80000000 and b == MASK32:
            return 0
        return trunc_rem(sa, sb) & MASK32
    if op == MD_REMU:
        return a if b == 0 else (a % b) & MASK32
    raise AssertionError(f"unknown md_op {op}")


async def check(dut, op: int, a: int, b: int) -> None:
    dut.a.value = a
    dut.b.value = b
    dut.md_op.value = op
    await Timer(1, unit="ns")
    got = int(dut.result.value)
    expected = model(op, a, b)
    assert got == expected, (
        f"FR-04/FR-11 violated: {NAMES[op]} a=0x{a:08x} b=0x{b:08x} -> "
        f"got 0x{got:08x}, expected 0x{expected:08x}"
    )


@cocotb.test()
async def test_edge_values(dut):
    """All eight operations over the corners of the 32-bit range."""
    for op in NAMES:
        for a in EDGE_VALUES:
            for b in EDGE_VALUES:
                await check(dut, op, a, b)


@cocotb.test()
async def test_division_by_zero(dut):
    """# REQ: FR-11 -- div = -1, divu = 0xFFFFFFFF, rem/remu = dividend."""
    for a in EDGE_VALUES:
        for op in (MD_DIV, MD_DIVU, MD_REM, MD_REMU):
            await check(dut, op, a, 0)


@cocotb.test()
async def test_signed_overflow(dut):
    """# REQ: FR-11 -- (-2^31) / -1 = -2^31 and (-2^31) rem -1 = 0."""
    await check(dut, MD_DIV, 0x80000000, 0xFFFFFFFF)
    await check(dut, MD_REM, 0x80000000, 0xFFFFFFFF)


@cocotb.test()
async def test_random(dut):
    random.seed(20260904)
    for _ in range(3000):
        op = random.choice(list(NAMES))
        await check(dut, op, random.getrandbits(32), random.getrandbits(32))
