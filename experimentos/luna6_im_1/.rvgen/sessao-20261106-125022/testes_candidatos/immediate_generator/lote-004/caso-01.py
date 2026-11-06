import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the legal SW instruction form used by this test."""
    match = re.fullmatch(
        r"\s*sw\s+x(\d+)\s*,\s*(-?(?:0[xX][0-9a-fA-F]+|\d+))\s*\(\s*x(\d+)\s*\)\s*",
        source,
    )
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2), 0)
    rs1 = int(match.group(3))

    if not (0 <= rs1 <= 31 and 0 <= rs2 <= 31):
        raise ValueError("register index is outside the RV32I range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("SW immediate is outside the signed 12-bit range")

    imm12 = immediate & 0xFFF
    return (
        (((imm12 >> 5) & 0x7F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (0x2 << 12)
        | ((imm12 & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def test_negative_sw_immediate_sign_extension(dut):
    # The positive witness uses offset 0x123; -1757 has the same low 11 bits.
    positive_witness = assemble_rv32i("sw x5, 291(x6)")
    negative_instruction = assemble_rv32i("sw x5, -1757(x6)")

    positive_s_low_11 = (
        (((positive_witness >> 25) & 0x7F) << 5)
        | ((positive_witness >> 7) & 0x1F)
    ) & 0x7FF
    negative_s_low_11 = (
        (((negative_instruction >> 25) & 0x7F) << 5)
        | ((negative_instruction >> 7) & 0x1F)
    ) & 0x7FF
    assert negative_s_low_11 == positive_s_low_11 == 0x123, (
        f"expected matching S-immediate low 11 bits 0x123, "
        f"observed positive 0x{positive_s_low_11:03X} and "
        f"negative 0x{negative_s_low_11:03X}"
    )

    dut.instr.value = negative_instruction
    await Timer(1, unit="ns")

    imm_s = int(dut.imm_s.value)
    assert (imm_s >> 12) == 0xFFFFF, (
        f"expected imm_s[31:12] = 0xFFFFF, observed 0x{imm_s >> 12:05X}"
    )
    assert (imm_s & 0xFFF) == 0x923, (
        f"expected imm_s[11:0] = 0x923, observed 0x{imm_s & 0xFFF:03X}"
    )
