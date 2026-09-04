#!/usr/bin/env python3
"""Testbench of the immediate generator.

# REQ: FR-03, FR-08

Reference model written straight from the instruction format tables of the
RISC-V unprivileged spec. This is the block where a transcription mistake is
easiest (B and J scatter their immediate bits), so the test drives random
instruction words and compares bit for bit, including the real instruction
words of a couple of known encodings.
"""
import random

import cocotb
from cocotb.triggers import Timer

MASK32 = 0xFFFFFFFF

IMM_I, IMM_S, IMM_B, IMM_U, IMM_J, IMM_NONE = 0, 1, 2, 3, 4, 7
NAMES = {IMM_I: "I", IMM_S: "S", IMM_B: "B", IMM_U: "U", IMM_J: "J"}


def bits(word: int, high: int, low: int) -> int:
    return (word >> low) & ((1 << (high - low + 1)) - 1)


def sign_extend(value: int, width: int) -> int:
    if value & (1 << (width - 1)):
        value -= 1 << width
    return value & MASK32


def model(fmt: int, instr: int) -> int:
    if fmt == IMM_I:
        return sign_extend(bits(instr, 31, 20), 12)
    if fmt == IMM_S:
        return sign_extend((bits(instr, 31, 25) << 5) | bits(instr, 11, 7), 12)
    if fmt == IMM_B:
        raw = ((bits(instr, 31, 31) << 12) | (bits(instr, 7, 7) << 11)
               | (bits(instr, 30, 25) << 5) | (bits(instr, 11, 8) << 1))
        return sign_extend(raw, 13)
    if fmt == IMM_U:
        return instr & 0xFFFFF000
    if fmt == IMM_J:
        raw = ((bits(instr, 31, 31) << 20) | (bits(instr, 19, 12) << 12)
               | (bits(instr, 20, 20) << 11) | (bits(instr, 30, 21) << 1))
        return sign_extend(raw, 21)
    raise AssertionError(f"unknown format {fmt}")


async def check(dut, fmt: int, instr: int) -> None:
    dut.instr.value = instr
    dut.imm_format.value = fmt
    await Timer(1, unit="ns")
    got = int(dut.imm.value)
    expected = model(fmt, instr)
    assert got == expected, (
        f"FR-03/FR-08 violated: format {NAMES[fmt]} instr=0x{instr:08x} -> "
        f"got 0x{got:08x}, expected 0x{expected:08x}"
    )


@cocotb.test()
async def test_random_words(dut):
    """All five formats over random instruction words."""
    random.seed(20260904)
    for _ in range(3000):
        instr = random.getrandbits(32)
        for fmt in NAMES:
            await check(dut, fmt, instr)


@cocotb.test()
async def test_all_ones_and_zeros(dut):
    """Sign extension corners: immediate all zeros and all ones."""
    for instr in (0x00000000, 0xFFFFFFFF, 0x80000000, 0x7FFFFFFF):
        for fmt in NAMES:
            await check(dut, fmt, instr)


@cocotb.test()
async def test_known_encodings(dut):
    """Real encodings produced by the assembler, checked by hand.

    Values taken from the RISC-V spec tables, not from this DUT:
      0xFEC42783  lw x15, -20(x8)     -> I immediate = -20
      0xFEF42623  sw x15, -20(x8)     -> S immediate = -20
      0xFE0796E3  bne x15, x0, -20    -> B immediate = -20
      0x00FC80B7  lui x1, 0xFC8       -> U immediate = 0x00FC8000
      0xFEDFF0EF  jal x1, -20         -> J immediate = -20
    """
    minus20 = (-20) & MASK32
    await check(dut, IMM_I, 0xFEC42783)
    assert int(dut.imm.value) == minus20
    await check(dut, IMM_S, 0xFEF42623)
    assert int(dut.imm.value) == minus20
    await check(dut, IMM_B, 0xFE0796E3)
    assert int(dut.imm.value) == minus20
    await check(dut, IMM_U, 0x00FC80B7)
    assert int(dut.imm.value) == 0x00FC8000
    await check(dut, IMM_J, 0xFEDFF0EF)
    assert int(dut.imm.value) == minus20


@cocotb.test()
async def test_no_format_is_zero(dut):
    """IMM_NONE (instruction without immediate) must produce zero."""
    dut.instr.value = 0xFFFFFFFF
    dut.imm_format.value = IMM_NONE
    await Timer(1, unit="ns")
    got = int(dut.imm.value)
    assert got == 0, f"IMM_NONE should give 0, got 0x{got:08x}"


@cocotb.test()
async def test_branch_and_jump_are_even(dut):
    """# REQ: FR-08 -- B and J immediates always have bit 0 clear."""
    random.seed(1234)
    for _ in range(500):
        instr = random.getrandbits(32)
        for fmt in (IMM_B, IMM_J):
            dut.instr.value = instr
            dut.imm_format.value = fmt
            await Timer(1, unit="ns")
            got = int(dut.imm.value)
            assert got & 1 == 0, (
                f"FR-08 violated: {NAMES[fmt]} immediate 0x{got:08x} is odd"
            )
