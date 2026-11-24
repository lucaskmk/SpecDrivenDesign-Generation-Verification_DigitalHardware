import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal ADDI source used by this test."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?(?:0[xX][0-9a-fA-F]+|[0-9]+))\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM source: {source}")

    rd = int(match.group(1))
    rs1 = int(match.group(2))
    immediate = int(match.group(3), 0)

    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("Register index must be in the range x0 through x31")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ADDI immediate must fit a signed 12-bit value")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_addi_immediate_bit_placement(dut):
    instr = assemble_rv32im("addi x5, x3, 0x5A3")
    dut.instr.value = instr
    await Timer(1, unit="ns")

    encoded_imm = (instr >> 20) & 0xFFF
    expected = encoded_imm if encoded_imm < 0x800 else encoded_imm | 0xFFFFF000
    observed = int(dut.imm_i.value)

    assert observed == expected, (
        f"imm_i: expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
