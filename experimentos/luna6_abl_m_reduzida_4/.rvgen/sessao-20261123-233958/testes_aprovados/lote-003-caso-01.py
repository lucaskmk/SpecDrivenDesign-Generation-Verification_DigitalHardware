import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the SW source used by this standalone test."""
    match = re.fullmatch(
        r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*",
        source,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))

    if not (0 <= rs1 < 32 and 0 <= rs2 < 32):
        raise ValueError("Register index is outside the RV32 register range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("SW immediate is outside the signed 12-bit range")

    imm = immediate & 0xFFF
    opcode = 0x23
    funct3 = 0x2
    return (
        ((imm >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | ((imm & 0x1F) << 7)
        | opcode
    )


@cocotb.test()
async def reset_suppresses_store_transaction(dut):
    store_instruction = assemble_rv32im("sw x0, 0(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = store_instruction
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    observed = int(dut.data_write.value)
    assert observed == 0, f"Expected data_write=0 during reset, observed {observed}"

    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed = int(dut.data_write.value)
    assert observed == 0, f"Expected data_write=0 during reset, observed {observed}"
