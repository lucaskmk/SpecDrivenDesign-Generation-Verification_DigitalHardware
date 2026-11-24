import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal SW instruction used by this test."""
    match = re.fullmatch(
        r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM assembly source: {source}")

    rs2, displacement, rs1 = map(int, match.groups())
    if not (0 <= rs1 < 32 and 0 <= rs2 < 32):
        raise ValueError("Register index must be between x0 and x31")
    if not (-2048 <= displacement <= 2047):
        raise ValueError("SW displacement must fit a signed 12-bit immediate")

    immediate = displacement & 0xFFF
    return (
        (((immediate >> 5) & 0x7F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (0x2 << 12)
        | ((immediate & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def negative_s_immediate_sign_extends(dut):
    dut.instr.value = 0x00000000
    await Timer(1, unit="ns")

    # -1 has the same low 11 encoded immediate bits as the positive
    # displacement 2047, with only the S-immediate sign bit changed.
    dut.instr.value = assemble_rv32im("sw x2, -1(x1)")
    await Timer(1, unit="ns")

    imm_s = int(dut.imm_s.value)
    assert (imm_s >> 12) == 0xFFFFF, (
        f"Expected imm_s upper bits 0xFFFFF, observed 0x{imm_s >> 12:05X}"
    )
    assert (imm_s & 0xFFF) == 0xFFF, (
        f"Expected imm_s low 12 bits 0xFFF, observed 0x{imm_s & 0xFFF:03X}"
    )
