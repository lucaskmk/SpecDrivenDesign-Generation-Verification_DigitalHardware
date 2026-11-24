import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_async_reset_clears_read_outputs(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.rs1_addr.value = 0x01
    dut.rs2_addr.value = 0x1F
    dut.rd_addr.value = 0x02
    dut.rd_data.value = 0xA5C30002
    dut.rd_write.value = 0

    await Timer(1, unit="ns")
    dut.rst.value = 1
    await Timer(1, unit="ns")

    assert (int(dut.rs1_data.value), int(dut.rs2_data.value)) == (0x00000000, 0x00000000), "After asynchronous reset, expected both read outputs to be 0x00000000"
