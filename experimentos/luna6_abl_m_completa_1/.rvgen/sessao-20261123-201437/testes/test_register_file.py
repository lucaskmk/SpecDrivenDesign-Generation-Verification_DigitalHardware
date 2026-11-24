import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_x0_reads_zero(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.read_addr1.value = 0x00
    dut.read_addr2.value = 0x00
    dut.write_enable.value = 0
    dut.write_addr.value = 0x01
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0x00000000, "Expected x0 to read 0x00000000"
