import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the ADDI source used by this test into an RV32I instruction."""
    match = re.fullmatch(r"\s*addi\s+x(\d+)\s*,\s*x(\d+)\s*,\s*(-?\d+)\s*", source)
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source}")

    rd = int(match.group(1))
    rs1 = int(match.group(2))
    immediate = int(match.group(3))

    if not 0 <= rd < 32 or not 0 <= rs1 < 32:
        raise ValueError("register index must be between x0 and x31")
    if not -(1 << 11) <= immediate < (1 << 11):
        raise ValueError("ADDI immediate must fit in signed 12 bits")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_non_store_inactive_data_bus_defaults(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = assemble_rv32i("addi x1, x0, 7")
    dut.data_read_data.value = 0x00000000

    dut.rst.value = 1
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    assert observed_write == 0, (
        f"expected data_write 0, observed {observed_write}"
    )

    observed_width = int(dut.data_width.value)
    assert observed_width == 0x2, (
        f"expected data_width 0x2, observed 0x{observed_width:X}"
    )

    observed_write_data = int(dut.data_write_data.value)
    assert observed_write_data == 0x00000000, (
        "expected data_write_data 0x00000000, "
        f"observed 0x{observed_write_data:08X}"
    )
