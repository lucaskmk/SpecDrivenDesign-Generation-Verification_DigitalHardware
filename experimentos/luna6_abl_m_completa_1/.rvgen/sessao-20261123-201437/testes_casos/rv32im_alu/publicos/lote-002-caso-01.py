import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the single legal ORI source instruction used by this test."""
    match = re.fullmatch(
        r"\s*ori\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*",
        source,
    )
    if match is None:
        raise ValueError(f"unsupported RV32IM source: {source!r}")

    rd, rs1 = int(match.group(1)), int(match.group(2))
    immediate = int(match.group(3), 0)
    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("register index is outside x0–x31")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ORI immediate is outside the signed 12-bit range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (0x6 << 12)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_ori_bitwise_or(dut):
    instruction = assemble_rv32im("ori x3, x5, 21")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F

    operand_a = 0x00000035
    operand_b = 0x00000015
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b

    await Timer(1, unit="ns")

    expected = operand_a | operand_b
    observed = int(dut.result.value)
    assert observed == expected, (
        f"expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
