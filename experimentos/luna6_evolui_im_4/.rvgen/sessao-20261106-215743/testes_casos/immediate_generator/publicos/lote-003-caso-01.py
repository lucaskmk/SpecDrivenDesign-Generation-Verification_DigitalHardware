import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the legal RV32I SW instruction used by this test."""
    match = re.fullmatch(r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\(x(\d+)\)\s*", source)
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))

    if not (0 <= rs1 < 32 and 0 <= rs2 < 32):
        raise ValueError("register index is outside the RV32I register range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("store immediate is outside the signed 12-bit range")

    immediate_bits = immediate & 0xFFF
    return (
        (((immediate_bits >> 5) & 0x7F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (0x2 << 12)
        | ((immediate_bits & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def test_s_type_split_immediate(dut):
    # The positive, nonuniform immediate 0x5A5 exercises both S-type slices.
    instruction = assemble_rv32i("sw x5, 1445(x3)")
    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_s.value)
    expected = 0x000005A5
    assert observed == expected, (
        f"expected imm_s=0x{expected:08X}, observed 0x{observed:08X}"
    )
