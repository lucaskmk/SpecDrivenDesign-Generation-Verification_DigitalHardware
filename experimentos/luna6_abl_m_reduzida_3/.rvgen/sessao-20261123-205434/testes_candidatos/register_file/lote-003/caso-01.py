import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_rs1_address_selects_asynchronously(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0xA5C30005
    dut.rd_write.value = 0

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    # Establish a known value in x5 with an accepted write.
    dut.rd_write.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    dut.rd_write.value = 0
    await Timer(1, unit="ns")

    # Confirm the support write, then change only rs1_addr without a clock edge.
    dut.rs1_addr.value = 0x05
    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == 0xA5C30005, (
        "Expected rs1_data 0xA5C30005 for x5, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )

    dut.rs1_addr.value = 0x00
    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == 0x00000000, (
        "Expected rs1_data 0x00000000 for x0, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )

    dut.rs1_addr.value = 0x05
    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == 0xA5C30005, (
        "Expected rs1_data 0xA5C30005 after selecting x5 again, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )
