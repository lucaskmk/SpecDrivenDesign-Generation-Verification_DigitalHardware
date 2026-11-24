import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ANDI source used by this test into a 32-bit instruction."""
    match = re.fullmatch(
        r"\s*andi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*",
        source,
    )
    if match is None:
        raise ValueError(f"unsupported RV32IM assembly source: {source!r}")

    rd = int(match.group(1))
    rs1 = int(match.group(2))
    immediate = int(match.group(3), 0)

    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("register number is outside the RV32 register range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ANDI immediate is outside the signed 12-bit range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (0x7 << 12)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_andi_bitwise_intersection(dut):
    instruction = assemble_rv32im("andi x5, x6, 819")

    dut.opcode.value = (instruction >> 0) & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x000005A5
    dut.operand_b.value = 0x00000333

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x00000121, (
        f"expected 0x00000121, observed 0x{observed:08X}"
    )
