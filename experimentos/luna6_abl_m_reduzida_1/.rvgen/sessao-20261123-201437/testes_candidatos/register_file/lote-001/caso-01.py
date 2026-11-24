import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_x0_ignores_enabled_write(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0
    dut.read_addr2.value = 0
    dut.write_enable.value = 1
    dut.write_addr.value = 0
    dut.write_data.value = 0xA5C39E71

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed1 = int(dut.read_data1.value)
    observed2 = int(dut.read_data2.value)
    assert observed1 == 0x00000000, (
        f"Expected read_data1 0x00000000 before the write edge, observed 0x{observed1:08X}"
    )
    assert observed2 == 0x00000000, (
        f"Expected read_data2 0x00000000 before the write edge, observed 0x{observed2:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed1 = int(dut.read_data1.value)
    observed2 = int(dut.read_data2.value)
    assert observed1 == 0x00000000, (
        f"Expected read_data1 0x00000000 after the attempted write, observed 0x{observed1:08X}"
    )
    assert observed2 == 0x00000000, (
        f"Expected read_data2 0x00000000 after the attempted write, observed 0x{observed2:08X}"
    )
