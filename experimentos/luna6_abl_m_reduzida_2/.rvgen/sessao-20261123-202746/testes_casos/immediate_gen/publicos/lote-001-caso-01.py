import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the LUI instruction used by this standalone test."""
    match = re.fullmatch(r"\s*lui\s+x(\d+)\s*,\s*(0x[0-9a-fA-F]+)\s*", source)
    if match is None:
        raise ValueError(f"Unsupported RV32IM assembly source: {source}")

    rd = int(match.group(1), 10)
    imm20 = int(match.group(2), 16)
    if not 0 <= rd <= 31 or not 0 <= imm20 <= 0xFFFFF:
        raise ValueError(f"Operand out of range in assembly source: {source}")

    return (imm20 << 12) | (rd << 7) | 0x37


@cocotb.test()
async def test_u_immediate_zero_extension(dut):
    instruction = assemble_rv32im("lui x5, 0xABCDE")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_u.value)
    expected_upper = (instruction >> 12) & 0xFFFFF
    observed_upper = (observed >> 12) & 0xFFFFF
    observed_lower = observed & 0xFFF

    assert observed_upper == expected_upper, (
        f"imm_u upper bits: expected 0x{expected_upper:05X}, "
        f"observed 0x{observed_upper:05X}"
    )
    assert observed_lower == 0x000, (
        f"imm_u lower bits: expected 0x000, observed 0x{observed_lower:03X}"
    )
