import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def rs1_read_tracks_address_asynchronously(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    await Timer(1, unit="ns")
    dut.rst.value = 0

    # Establish a nonzero value in x5 using the write port.
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0x12345678
    dut.rd_write.value = 1
    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    dut.rd_write.value = 0
    await Timer(1, unit="ns")

    # Keep rs2_addr fixed and change rs1_addr without a clock edge.
    dut.rs1_addr.value = 0x05
    await Timer(1, unit="ns")
    observed_x5 = int(dut.rs1_data.value)
    assert observed_x5 == 0x12345678, (
        f"Expected rs1_data 0x12345678 for rs1_addr x5; "
        f"observed {observed_x5:#010x}"
    )

    dut.rs1_addr.value = 0x00
    await Timer(1, unit="ns")
    observed_x0 = int(dut.rs1_data.value)
    assert observed_x0 == 0x00000000, (
        f"Expected rs1_data 0x00000000 for rs1_addr x0; "
        f"observed {observed_x0:#010x}"
    )
