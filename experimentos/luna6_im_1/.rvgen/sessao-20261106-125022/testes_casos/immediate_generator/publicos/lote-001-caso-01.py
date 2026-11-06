import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the ADDI source used by this standalone test."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+)\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source!r}")

    rd, rs1, immediate = (int(value) for value in match.groups())
    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("register number is outside the RV32I range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ADDI immediate is outside the signed 12-bit range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_i_immediate_zero_extension_when_sign_clear(dut):
    support_instr = assemble_rv32i("addi x1, x2, -1365")
    target_instr = assemble_rv32i("addi x1, x2, 683")

    assert support_instr ^ target_instr == 0x80000000, (
        "support and target instructions must differ only in instr[31]"
    )

    dut.instr.value = support_instr
    await Timer(1, unit="ns")

    dut.instr.value = target_instr
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    expected = (target_instr >> 20) & 0xFFF

    assert observed & 0xFFFFF000 == 0, (
        f"expected imm_i[31:12] to be 0x00000000, "
        f"observed 0x{observed:08X}"
    )
    assert observed & 0x00000FFF == expected, (
        f"expected imm_i[11:0] to be 0x{expected:03X}, "
        f"observed 0x{observed & 0x00000FFF:03X}"
    )
