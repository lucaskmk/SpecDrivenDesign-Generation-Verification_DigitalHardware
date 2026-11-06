import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def write_nonzero_register_and_read_back(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == 0x00000000, (
        "Expected reset baseline 0x00000000 for x5; "
        f"observed {int(dut.rs1_data.value):#010x}"
    )

    dut.rst.value = 0
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0xA5C37E19
    dut.rd_write.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.rs1_data.value) == 0xA5C37E19, (
        "Expected x5 readback 0xA5C37E19 after the qualifying write; "
        f"observed {int(dut.rs1_data.value):#010x}"
    )
