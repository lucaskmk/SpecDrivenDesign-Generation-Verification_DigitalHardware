import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def reset_reads_zero(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x1F
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0xFFFFFFFF
    dut.rd_write.value = 0

    await Timer(1, unit="ns")

    assert (int(dut.rs1_data.value), int(dut.rs2_data.value)) == (0x00000000, 0x00000000), (
        "Expected reset reads 0x00000000 on both ports; observed "
        f"({int(dut.rs1_data.value):#010x}, {int(dut.rs2_data.value):#010x})"
    )
