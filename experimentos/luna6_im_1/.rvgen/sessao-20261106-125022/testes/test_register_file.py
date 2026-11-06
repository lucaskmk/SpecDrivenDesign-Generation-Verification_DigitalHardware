import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_register_file_reset_output(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x0
    dut.read_addr2.value = 0x0
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x00000000, "Expected read_data1=0x00000000 during reset"
