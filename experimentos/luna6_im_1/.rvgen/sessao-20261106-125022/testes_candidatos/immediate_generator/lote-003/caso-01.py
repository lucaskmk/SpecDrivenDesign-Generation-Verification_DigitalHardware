import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source: str) -> int:
    """Assemble the legal RV32I SW source used by this test."""
    match = re.fullmatch(
        r"\s*sw\s+x(\d+)\s*,\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*\(\s*x(\d+)\s*\)\s*",
        source,
    )
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2), 0)
    rs1 = int(match.group(3))

    if not 0 <= rs1 < 32 or not 0 <= rs2 < 32:
        raise ValueError("register number must be in the range x0 through x31")
    if not -2048 <= immediate <= 2047:
        raise ValueError("SW immediate is outside the signed 12-bit range")

    encoded_immediate = immediate & 0xFFF
    return (
        (((encoded_immediate >> 5) & 0x7F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (0x2 << 12)
        | ((encoded_immediate & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def test_sw_s_immediate_source_field_mapping(dut):
    instruction = assemble_rv32i("sw x7, 0x6A8(x9)")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    upper_field = (instruction >> 25) & 0x7F
    lower_field = (instruction >> 7) & 0x1F
    expected = (upper_field << 5) | lower_field
    observed = int(dut.imm_s.value)

    assert expected == 0x000006A8, (
        f"expected assembled S immediate 0x000006A8, observed 0x{expected:08X}"
    )
    assert observed == expected, (
        f"expected imm_s 0x{expected:08X}, observed 0x{observed:08X}"
    )
