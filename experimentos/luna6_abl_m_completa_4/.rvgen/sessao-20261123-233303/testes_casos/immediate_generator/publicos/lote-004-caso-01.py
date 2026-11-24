import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the legal SW instruction used by this test."""
    match = re.fullmatch(r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*", source)
    assert match is not None, f"unsupported assembly source: {source!r}"

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))

    assert 0 <= rs1 < 32 and 0 <= rs2 < 32, "register index must be in 0..31"
    assert -2048 <= immediate <= 2047, "SW immediate must fit signed 12 bits"

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
async def test_s_type_split_field_reconstruction(dut):
    instruction = assemble_rv32im("sw x13, -677(x9)")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    imm12 = (-677) & 0xFFF
    expected = imm12 | (0xFFFFF000 if imm12 & 0x800 else 0)

    observed = int(dut.imm_s.value)
    assert observed == expected, (
        f"expected imm_s 0x{expected:08X} for S-type immediate 0x{imm12:03X}, "
        f"observed 0x{observed:08X}"
    )
