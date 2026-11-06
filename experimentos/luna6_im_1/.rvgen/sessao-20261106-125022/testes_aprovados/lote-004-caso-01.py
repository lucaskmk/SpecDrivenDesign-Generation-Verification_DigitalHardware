import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source: str) -> int:
    """Assemble the SW source used by this test."""
    match = re.fullmatch(r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*", source, re.IGNORECASE)
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))
    if not (0 <= rs1 < 32 and 0 <= rs2 < 32 and -2048 <= immediate <= 2047):
        raise ValueError(f"SW operand out of range: {source!r}")

    imm = immediate & 0xFFF
    return (
        (((imm >> 5) & 0x7F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (0b010 << 12)
        | ((imm & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def test_reset_suppresses_store_write(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = assemble_rv32i("sw x0, 0(x0)")
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed_addr = int(dut.instr_addr.value)
    assert observed_addr == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, observed 0x{observed_addr:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 0, (
        f"expected data_write 0 during reset, observed {observed_write}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")
    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected legal SW to assert data_write outside reset, observed {observed_write}"
    )

    dut.rst.value = 1
    await Timer(1, unit="ns")
    observed_addr = int(dut.instr_addr.value)
    assert observed_addr == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, observed 0x{observed_addr:08X}"
    )
    observed_write = int(dut.data_write.value)
    assert observed_write == 0, (
        f"expected data_write 0 during reset, observed {observed_write}"
    )
