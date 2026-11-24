import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the SB instruction form used by this standalone test."""
    match = re.fullmatch(
        r"\s*sb\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*",
        source,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"unsupported RV32IM source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))

    if not (0 <= rs1 < 32 and 0 <= rs2 < 32):
        raise ValueError("register index must be between x0 and x31")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("SB immediate must fit in a signed 12-bit value")

    imm12 = immediate & 0xFFF
    return (
        (((imm12 >> 5) & 0x7F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (0b000 << 12)
        | ((imm12 & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def sb_x0_presents_byte_store_transaction(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = assemble_rv32im("sb x0, 0(x0)")
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    instr_addr = int(dut.instr_addr.value)
    assert instr_addr == 0x00000000, (
        f"expected instr_addr 0x00000000, observed 0x{instr_addr:08X}"
    )

    data_write = int(dut.data_write.value)
    assert data_write == 1, f"expected data_write 1, observed {data_write}"

    data_width = int(dut.data_width.value)
    assert data_width == 0x0, f"expected data_width 0x0, observed 0x{data_width:X}"

    data_addr = int(dut.data_addr.value)
    assert data_addr == 0x00000000, (
        f"expected data_addr 0x00000000, observed 0x{data_addr:08X}"
    )

    data_write_data = int(dut.data_write_data.value)
    assert data_write_data == 0x00000000, (
        f"expected data_write_data 0x00000000, observed 0x{data_write_data:08X}"
    )
