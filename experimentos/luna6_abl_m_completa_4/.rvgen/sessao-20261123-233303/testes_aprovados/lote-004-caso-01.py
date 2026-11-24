import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the ADDI form used by this test from legal RV32IM source."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?(?:0x[0-9a-fA-F]+|\d+))\s*",
        source,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM source: {source!r}")

    rd = int(match.group(1))
    rs1 = int(match.group(2))
    immediate = int(match.group(3), 0)
    if not (0 <= rd < 32 and 0 <= rs1 < 32 and -2048 <= immediate <= 2047):
        raise ValueError(f"ADDI operand out of range: {source!r}")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def reset_release_alone_does_not_advance_pc(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = assemble_rv32im("addi x0, x0, 0")
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    address_before_release = int(dut.instr_addr.value)
    assert address_before_release == 0x00000000, (
        f"Expected reset instr_addr=0x00000000, "
        f"observed 0x{address_before_release:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    address_after_release = int(dut.instr_addr.value)
    assert address_after_release == address_before_release, (
        f"Expected instr_addr to remain 0x{address_before_release:08X} "
        f"after reset release without a clock transition, "
        f"observed 0x{address_after_release:08X}"
    )
