import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the legal RV32IM SW instruction used by this test."""
    match = re.fullmatch(r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*", source)
    if match is None:
        raise ValueError(f"Unsupported RV32IM source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))

    if not (0 <= rs1 < 32 and 0 <= rs2 < 32 and -2048 <= immediate <= 2047):
        raise ValueError(f"Operand out of range: {source!r}")

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
async def test_s_immediate_split_fields(dut):
    instruction = assemble_rv32im("sw x9, 1443(x6)")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_s.value)
    expected = 0x000005A3
    assert observed == expected, (
        f"imm_s: expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
