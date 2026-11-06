import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source: str) -> int:
    """Assemble one legal ADDI instruction and return its 32-bit word."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?(?:0[xX][0-9a-fA-F]+|\d+))\s*",
        source,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32I assembly source: {source!r}")

    rd = int(match.group(1))
    rs1 = int(match.group(2))
    immediate = int(match.group(3), 0)

    if not (0 <= rd <= 31 and 0 <= rs1 <= 31):
        raise ValueError("Register index is outside the RV32I register range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ADDI immediate is outside the signed 12-bit range")

    imm12 = immediate & 0xFFF
    return (imm12 << 20) | (rs1 << 15) | (rd << 7) | 0x13


@cocotb.test()
async def test_u_immediate_from_legal_addi(dut):
    instruction = assemble_rv32i("addi x5, x6, -173")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    expected = instruction & 0xFFFFF000
    observed = int(dut.imm_u.value)
    assert observed == expected, (
        f"expected imm_u=0x{expected:08X}, observed 0x{observed:08X}"
    )
