import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the LUI source used by this test and return its 32-bit word."""
    match = re.fullmatch(
        r"\s*lui\s+x([0-9]+)\s*,\s*(0x[0-9a-fA-F]+|[0-9]+)\s*",
        source,
    )
    if match is None:
        raise ValueError(f"unsupported RV32IM source: {source!r}")

    rd = int(match.group(1))
    upper_immediate = int(match.group(2), 0)
    if not 0 <= rd <= 31 or not 0 <= upper_immediate <= 0xFFFFF:
        raise ValueError(f"out-of-range LUI operand in source: {source!r}")

    return (upper_immediate << 12) | (rd << 7) | 0x37


@cocotb.test()
async def test_lui_u_type_immediate(dut):
    instruction = assemble_rv32im("lui x7, 0xA5C39")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    expected = instruction & 0xFFFFF000
    observed = int(dut.imm_u.value)
    assert observed == expected, (
        f"expected imm_u 0x{expected:08X}, observed 0x{observed:08X}"
    )
