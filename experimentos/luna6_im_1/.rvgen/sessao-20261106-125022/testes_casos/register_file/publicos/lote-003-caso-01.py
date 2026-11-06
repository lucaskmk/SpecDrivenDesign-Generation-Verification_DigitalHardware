import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_enabled_write_to_x0_is_ignored(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x1
    dut.read_addr2.value = 0x1
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0xA5C39E71

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.write_enable.value = 1
    dut.write_addr.value = 0x0
    dut.write_data.value = 0xA5C39E71

    dut.clk.value = 1
    await Timer(1, unit="ns")

    dut.write_enable.value = 0
    dut.read_addr1.value = 0x0
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x00000000, (
        "Expected read_data1=0x00000000 after an enabled write to x0"
    )
