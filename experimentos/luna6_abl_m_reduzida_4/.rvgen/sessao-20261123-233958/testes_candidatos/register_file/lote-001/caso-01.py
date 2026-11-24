import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_reset_deassertion_preserves_cleared_registers(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.rs1_addr.value = 0x5
    dut.rs2_addr.value = 0x11
    dut.rd_addr.value = 0x0
    dut.rd_data.value = 0x12345678
    dut.rd_write.value = 0

    dut.rst.value = 1
    await Timer(1, unit="ns")

    during_reset = (int(dut.rs1_data.value), int(dut.rs2_data.value))
    assert during_reset == (0x00000000, 0x00000000), (
        f"Expected reset outputs (0x00000000, 0x00000000), observed {during_reset}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    after_deassertion = (int(dut.rs1_data.value), int(dut.rs2_data.value))
    assert after_deassertion == (0x00000000, 0x00000000), (
        "Expected outputs to remain (0x00000000, 0x00000000) after reset "
        f"deassertion without a clock edge, observed {after_deassertion}"
    )
