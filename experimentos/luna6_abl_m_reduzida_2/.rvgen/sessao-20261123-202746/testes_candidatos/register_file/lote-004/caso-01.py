import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def rs2_read_selection_is_independent(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x0
    dut.rs2_addr.value = 0x0
    dut.rd_addr.value = 0x0
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    await Timer(1, unit="ns")

    dut.rst.value = 0
    dut.rd_addr.value = 0x7
    dut.rd_data.value = 0xA5C39E71
    dut.rd_write.value = 1
    dut.clk.value = 1
    await Timer(1, unit="ns")

    dut.clk.value = 0
    dut.rd_write.value = 0
    dut.rs1_addr.value = 0x0
    dut.rs2_addr.value = 0x0
    await Timer(1, unit="ns")

    dut.rs2_addr.value = 0x7
    await Timer(1, unit="ns")

    observed_rs1 = int(dut.rs1_data.value)
    observed_rs2 = int(dut.rs2_data.value)
    assert (observed_rs1, observed_rs2) == (0x00000000, 0xA5C39E71), (
        f"expected rs1_data=0x00000000 and rs2_data=0xA5C39E71, "
        f"observed rs1_data=0x{observed_rs1:08X} and "
        f"rs2_data=0x{observed_rs2:08X}"
    )
