import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble one legal ADDI instruction from RV32I assembly source."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+)\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"unsupported RV32I assembly source: {source!r}")

    rd, rs1, immediate = (int(field) for field in match.groups())
    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("register indices must be in the range x0 through x31")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ADDI immediate must fit in signed 12 bits")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_positive_odd_i_immediate_zero_extension(dut):
    instruction = assemble_rv32i("addi x1, x0, 5")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    expected = 0x00000005
    assert observed == expected, (
        f"expected imm_i=0x{expected:08X}, observed 0x{observed:08X}"
    )

    upper_bits = observed & 0xFFFFF000
    assert upper_bits == 0x00000000, (
        f"expected imm_i upper bits=0x00000000, observed 0x{upper_bits:08X}"
    )

    low_bit = observed & 0x00000001
    assert low_bit == 0x00000001, (
        f"expected imm_i low bit=0x1, observed 0x{low_bit:X}"
    )
