import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def committed_nonzero_write_is_read_asynchronously(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x07
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0xFFFFFFFF
    dut.rd_write.value = 0

    await Timer(1, unit="ns")

    observed = (int(dut.rs1_data.value), int(dut.rs2_data.value))
    assert observed == (0x00000000, 0x00000000), (
        f"expected reset read outputs (0x00000000, 0x00000000), "
        f"observed (0x{observed[0]:08X}, 0x{observed[1]:08X})"
    )

    dut.rst.value = 0
    dut.rd_write.value = 1
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x12345678
    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed_x0 = int(dut.rs2_data.value)
    assert observed_x0 == 0x00000000, (
        f"expected x0 read 0x00000000 after an x0 write, "
        f"observed 0x{observed_x0:08X}"
    )

    dut.clk.value = 0
    await Timer(1, unit="ns")

    dut.rd_addr.value = 0x07
    dut.rd_data.value = 0xA5C39E71
    dut.rs1_addr.value = 0x07
    dut.rd_write.value = 1
    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed_value = int(dut.rs1_data.value)
    assert observed_value == 0xA5C39E71, (
        f"expected register x7 read 0xA5C39E71, "
        f"observed 0x{observed_value:08X}"
    )
