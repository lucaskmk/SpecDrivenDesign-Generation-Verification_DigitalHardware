# REQ: FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09, NFR-03
import random

import cocotb
from cocotb.triggers import Timer

MASK32 = (1 << 32) - 1


def signed32(value):
    return value - (1 << 32) if value & (1 << 31) else value


def expected_result(a, b, control):
    if control == 0x0:
        return a & b
    if control == 0x1:
        return a | b
    if control == 0x2:
        return (a + b) & MASK32
    if control == 0x6:
        return (a - b) & MASK32
    if control == 0x7:
        return int(signed32(a) < signed32(b))
    if control == 0xC:
        return ~(a | b) & MASK32
    return 0


async def check_operation(dut, a, b, control):
    dut.a.value = a
    dut.b.value = b
    dut.alu_control.value = control
    await Timer(1, unit="ns")

    expected = expected_result(a, b, control)
    assert int(dut.result.value) == expected, (
        f"control={control:04b}, a=0x{a:08X}, b=0x{b:08X}: "
        f"expected 0x{expected:08X}, got {dut.result.value}"
    )
    assert int(dut.zero.value) == int(expected == 0)


@cocotb.test()
async def test_mips_alu_operations(dut):
    vectors = [
        (0x00000000, 0x00000000),
        (0xFFFFFFFF, 0x00000000),
        (0x7FFFFFFF, 0x00000001),
        (0x80000000, 0x00000001),
        (0x12345678, 0xFEDCBA98),
    ]
    for control in (0x0, 0x1, 0x2, 0x6, 0x7, 0xC):
        for a, b in vectors:
            await check_operation(dut, a, b, control)


@cocotb.test()
async def test_mips_alu_random_vectors(dut):
    random.seed(32)
    for control in (0x0, 0x1, 0x2, 0x6, 0x7, 0xC):
        for _ in range(32):
            await check_operation(dut, random.getrandbits(32), random.getrandbits(32), control)


@cocotb.test()
async def test_unsupported_control_is_deterministic(dut):
    for control in (0x3, 0x4, 0x5, 0x8, 0x9, 0xA, 0xB, 0xD, 0xE, 0xF):
        await check_operation(dut, 0x12345678, 0x9ABCDEF0, control)
