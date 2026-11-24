import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_enabled_write_updates_selected_register(dut):
    destination = 0x05
    write_value = 0xA5C39E71

    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = destination
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = destination
    dut.rd_data.value = write_value
    dut.rd_write.value = 0

    await Timer(1, unit="ns")
    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"Expected selected read output 0x00000000 during reset, "
        f"observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")
    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"Expected selected read output 0x00000000 after reset deassertion "
        f"without a clock edge, observed 0x{observed:08X}"
    )

    dut.rd_write.value = 1
    await Timer(1, unit="ns")
    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"Expected selected read output 0x00000000 before the write edge, "
        f"observed 0x{observed:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    observed = int(dut.rs1_data.value)
    assert observed == write_value, (
        f"Expected selected read output 0x{write_value:08X} after the write "
        f"edge, observed 0x{observed:08X}"
    )
