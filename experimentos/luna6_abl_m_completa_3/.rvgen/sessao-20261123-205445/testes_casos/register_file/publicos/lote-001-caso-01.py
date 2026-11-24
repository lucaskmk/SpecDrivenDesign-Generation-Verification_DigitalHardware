import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_x0_reads_stay_zero_during_write_to_x0(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0xA5C37E19
    dut.rd_write.value = 1

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    assert int(dut.rs1_data.value) == 0x00000000, (
        f"Expected 0x00000000 on rs1_data, observed "
        f"0x{int(dut.rs1_data.value):08X}"
    )
    assert int(dut.rs2_data.value) == 0x00000000, (
        f"Expected 0x00000000 on rs2_data, observed "
        f"0x{int(dut.rs2_data.value):08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")

    assert int(dut.rs1_data.value) == 0x00000000, (
        f"Expected 0x00000000 on rs1_data after the write edge, observed "
        f"0x{int(dut.rs1_data.value):08X}"
    )
    assert int(dut.rs2_data.value) == 0x00000000, (
        f"Expected 0x00000000 on rs2_data after the write edge, observed "
        f"0x{int(dut.rs2_data.value):08X}"
    )
