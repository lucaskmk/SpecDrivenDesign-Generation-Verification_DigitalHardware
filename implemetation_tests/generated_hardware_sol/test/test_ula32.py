"""Cocotb verification for the 32-bit MIPS-style ULA."""

# REQ: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, NFR-03

import random

import cocotb
from cocotb.triggers import Timer

MASK32 = 0xFFFFFFFF

OPERATIONS = {
    0b0000: lambda a, b: a & b,
    0b0001: lambda a, b: a | b,
    0b0010: lambda a, b: (a + b) & MASK32,
    0b0110: lambda a, b: (a - b) & MASK32,
    0b0111: lambda a, b: int(to_signed(a) < to_signed(b)),
    0b1100: lambda a, b: (~(a | b)) & MASK32,
}


def to_signed(value):
    return value if value < 0x80000000 else value - 0x100000000


async def check_vector(dut, a, b, control, expected=None):
    dut.a.value = a
    dut.b.value = b
    dut.alu_control.value = control
    await Timer(1, unit="ns")

    if expected is None:
        operation = OPERATIONS.get(control)
        expected = operation(a, b) if operation else 0

    actual = int(dut.result.value)
    actual_zero = int(dut.zero.value)
    assert actual == expected, (
        f"control={control:04b}, a=0x{a:08X}, b=0x{b:08X}: "
        f"expected 0x{expected:08X}, got 0x{actual:08X}"
    )
    assert actual_zero == int(expected == 0), (
        f"FR-03: result=0x{actual:08X}, expected zero={int(expected == 0)}, "
        f"got {actual_zero}"
    )


@cocotb.test()
async def test_directed_operations_and_flags(dut):
    """REQ: FR-02, FR-03, FR-05, FR-06."""
    vectors = [
        (0xAAAAAAAA, 0x0F0F0F0F, 0b0000, 0x0A0A0A0A),
        (0xA0000000, 0x0F00000F, 0b0001, 0xAF00000F),
        (0xFFFFFFFF, 0x00000001, 0b0010, 0x00000000),
        (0x7FFFFFFF, 0x00000001, 0b0010, 0x80000000),
        (0x00000000, 0x00000001, 0b0110, 0xFFFFFFFF),
        (0x12345678, 0x12345678, 0b0110, 0x00000000),
        (0xFFFFFFFF, 0x00000000, 0b0111, 0x00000001),
        (0x7FFFFFFF, 0x80000000, 0b0111, 0x00000000),
        (0x80000000, 0x7FFFFFFF, 0b0111, 0x00000001),
        (0xFFFFFFFF, 0x00000000, 0b1100, 0x00000000),
        (0x00000000, 0x00000000, 0b1100, 0xFFFFFFFF),
    ]
    for a, b, control, expected in vectors:
        await check_vector(dut, a, b, control, expected)


@cocotb.test()
async def test_all_undefined_controls(dut):
    """REQ: FR-04."""
    undefined = set(range(16)) - set(OPERATIONS)
    for control in sorted(undefined):
        await check_vector(dut, 0x12345678, 0x9ABCDEF0, control, 0)


@cocotb.test()
async def test_randomized_reference_model(dut):
    """REQ: FR-02, FR-03, FR-05, FR-06."""
    rng = random.Random(0x32A1)
    for control in OPERATIONS:
        for _ in range(200):
            await check_vector(
                dut,
                rng.getrandbits(32),
                rng.getrandbits(32),
                control,
            )
