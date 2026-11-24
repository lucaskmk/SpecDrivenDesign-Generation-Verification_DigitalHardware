import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_enabled_write_to_x0_is_ignored(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x0
    dut.rs2_addr.value = 0x0
    dut.rd_addr.value = 0x0
    dut.rd_data.value = 0xA5C39E71
    dut.rd_write.value = 0

    await Timer(1, unit="ns")

    dut.rd_write.value = 1
    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed = (int(dut.rs1_data.value), int(dut.rs2_data.value))
    expected = (0x00000000, 0x00000000)
    assert observed == expected, (
        f"Expected both x0 reads to be 0x00000000 after enabled write "
        f"of 0xA5C39E71, observed "
        f"(0x{observed[0]:08X}, 0x{observed[1]:08X})"
    )
