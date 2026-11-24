import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ADDI source used by this test into one RV32IM instruction."""
    match = re.fullmatch(
        r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+)\s*",
        source,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported assembly source: {source!r}")

    rd, rs1, immediate = (int(field) for field in match.groups())
    if not (0 <= rd < 32 and 0 <= rs1 < 32 and -2048 <= immediate < 2048):
        raise ValueError(f"Invalid ADDI operands: {source!r}")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def reset_holds_pc_across_rising_edge(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = assemble_rv32im("addi x1, x0, 1")
    dut.data_read_data.value = 0x00000000

    # Establish the asynchronous-reset witness before the rising edge.
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 before the edge during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    # Keep reset asserted while presenting the rising edge.
    dut.clk.value = 1
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr=0x00000000 after the edge during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
