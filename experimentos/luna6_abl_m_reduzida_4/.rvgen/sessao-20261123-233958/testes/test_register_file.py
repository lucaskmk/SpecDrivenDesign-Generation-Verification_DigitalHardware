import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_async_reset_clears_read_outputs(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x1
    dut.rs2_addr.value = 0x1F
    dut.rd_addr.value = 0x0
    dut.rd_data.value = 0x12345678
    dut.rd_write.value = 0

    await Timer(1, unit="ns")

    observed = (int(dut.rs1_data.value), int(dut.rs2_data.value))
    assert observed == (0x00000000, 0x00000000), (
        f"Expected reset outputs (0x00000000, 0x00000000), observed {observed}"
    )
