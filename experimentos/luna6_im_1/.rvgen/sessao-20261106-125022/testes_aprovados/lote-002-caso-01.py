import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source: str) -> int:
    """Assemble the legal SW source used by this test."""
    match = re.fullmatch(
        r"\s*sw\s+x(\d+)\s*,\s*(-?\d+)\s*\(\s*x(\d+)\s*\)\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))
    if not (0 <= rs1 < 32 and 0 <= rs2 < 32):
        raise ValueError("register index must be between x0 and x31")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("store immediate must fit a signed 12-bit value")

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
async def test_sw_x0_presents_zero_on_store_data_bus(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    dut.rst.value = 1
    await Timer(1, unit="ns")

    dut.instr_data.value = assemble_rv32i("sw x0, 0(x0)")
    await Timer(1, unit="ns")

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected data_write 1 for SW, observed {observed_write}"
    )

    observed_data = int(dut.data_write_data.value)
    assert observed_data == 0x00000000, (
        f"expected data_write_data 0x00000000, observed 0x{observed_data:08X}"
    )
