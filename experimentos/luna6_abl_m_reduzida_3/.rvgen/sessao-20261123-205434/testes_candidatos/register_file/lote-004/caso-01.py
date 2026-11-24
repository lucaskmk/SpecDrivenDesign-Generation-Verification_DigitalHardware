import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_rs2_async_selection(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    await Timer(1, unit="ns")
    dut.rst.value = 1
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    expected = 0xA5C30005
    dut.rd_addr.value = 0x05
    dut.rd_data.value = expected
    dut.rd_write.value = 1
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed = int(dut.rs1_data.value)
    assert observed == expected, (
        f"Expected the accepted write to establish 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )

    dut.rd_write.value = 0
    dut.clk.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.rs2_data.value)
    assert observed == 0x00000000, (
        f"Expected rs2 x0 to read 0x00000000, observed 0x{observed:08X}"
    )

    # Change only the rs2 address while the clock remains low.
    dut.rs2_addr.value = 0x05
    await Timer(1, unit="ns")

    observed = int(dut.rs2_data.value)
    assert observed == expected, (
        f"Expected asynchronous rs2 selection to return 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )
