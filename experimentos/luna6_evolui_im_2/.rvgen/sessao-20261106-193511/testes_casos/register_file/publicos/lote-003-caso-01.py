import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def rs2_asynchronous_selection_independent_of_rs1(dut):
    # Initialize every input and provide a public-port reset witness.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    await Timer(1, unit="ns")

    rs1_during_reset = int(dut.rs1_data.value)
    rs2_during_reset = int(dut.rs2_data.value)
    assert (rs1_during_reset, rs2_during_reset) == (0x00000000, 0x00000000), (
        "Expected reset reads (0x00000000, 0x00000000); observed "
        f"({rs1_during_reset:#010x}, {rs2_during_reset:#010x})"
    )

    # Establish the stored value as support for the asynchronous-read check.
    dut.rst.value = 0
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0xA5C37E19
    dut.rd_write.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")

    dut.rd_write.value = 0
    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    await Timer(1, unit="ns")

    rs1_zero = int(dut.rs1_data.value)
    rs2_zero = int(dut.rs2_data.value)
    assert (rs1_zero, rs2_zero) == (0x00000000, 0x00000000), (
        "Expected both x0 reads to be 0x00000000 before changing rs2_addr; "
        f"observed ({rs1_zero:#010x}, {rs2_zero:#010x})"
    )

    # Change only rs2_addr and observe the result without another clock edge.
    dut.rs2_addr.value = 0x05
    await Timer(1, unit="ns")

    rs1_observed = int(dut.rs1_data.value)
    rs2_observed = int(dut.rs2_data.value)
    assert (rs1_observed, rs2_observed) == (0x00000000, 0xA5C37E19), (
        "Expected rs1_data to remain 0x00000000 and rs2_data to asynchronously "
        f"show 0xA5C37E19; observed ({rs1_observed:#010x}, "
        f"{rs2_observed:#010x})"
    )
