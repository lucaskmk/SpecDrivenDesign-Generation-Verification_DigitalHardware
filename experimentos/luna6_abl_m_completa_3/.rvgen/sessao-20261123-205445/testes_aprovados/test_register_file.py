import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_async_reset_clears_read_output(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x01
    dut.rs2_addr.value = 0x1F
    dut.rd_addr.value = 0x01
    dut.rd_data.value = 0x12345678
    dut.rd_write.value = 0
    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == 0x00000000, f"Expected 0x00000000 after reset, observed 0x{int(dut.rs1_data.value):08X}"
