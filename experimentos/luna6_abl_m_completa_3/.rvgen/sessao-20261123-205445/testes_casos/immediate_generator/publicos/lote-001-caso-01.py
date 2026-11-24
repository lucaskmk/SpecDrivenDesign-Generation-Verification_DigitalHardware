import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ADDI source used by this test."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+)\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM assembly source: {source!r}")

    rd, rs1, immediate = (int(field) for field in match.groups())
    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("Register index is outside the RV32 register file")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ADDI immediate is outside the signed 12-bit range")

    encoded_immediate = immediate & 0xFFF
    return (
        (encoded_immediate << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_addi_negative_immediate_sign_extension(dut):
    immediate = -53
    instruction = assemble_rv32im(f"addi x5, x6, {immediate}")

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    expected_low = immediate & 0xFFF
    observed = int(dut.imm_i.value)
    expected = 0xFFFFF000 | expected_low

    assert observed & 0xFFF == expected_low, (
        f"imm_i[11:0] expected 0x{expected_low:03X}, "
        f"observed 0x{observed & 0xFFF:03X}"
    )
    assert observed >> 12 == 0xFFFFF, (
        f"imm_i[31:12] expected 0xFFFFF, observed 0x{observed >> 12:05X}"
    )
    assert observed == expected, (
        f"imm_i expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
