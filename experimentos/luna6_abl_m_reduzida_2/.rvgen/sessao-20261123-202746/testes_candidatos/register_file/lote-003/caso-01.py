import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def asynchronous_read_address_selects_written_register(dut):
    # Initialize every input and assert asynchronous reset.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0
    await Timer(1, unit="ns")

    # Release reset and write a known value to x7.
    dut.rst.value = 0
    dut.rd_addr.value = 0x07
    dut.rd_data.value = 0xA1B2C3D4
    dut.rd_write.value = 1
    dut.clk.value = 1
    await Timer(1, unit="ns")

    # Hold the clock low and disable writes while checking asynchronous reads.
    dut.clk.value = 0
    dut.rd_write.value = 0
    await Timer(1, unit="ns")

    observed_x0 = int(dut.rs1_data.value)
    assert observed_x0 == 0x00000000, (
        f"expected x0 read 0x00000000, observed 0x{observed_x0:08X}"
    )

    # Change only the read address; no clock transition occurs here.
    dut.rs1_addr.value = 0x07
    await Timer(1, unit="ns")

    observed_x7 = int(dut.rs1_data.value)
    assert observed_x7 == 0xA1B2C3D4, (
        f"expected x7 read 0xA1B2C3D4, observed 0x{observed_x7:08X}"
    )
