import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def write_to_x0_has_no_effect(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x1F
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0xA5A55A5A
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.rd_write.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    await Timer(1, unit="ns")

    rs1_observed = int(dut.rs1_data.value)
    rs2_observed = int(dut.rs2_data.value)
    assert (rs1_observed, rs2_observed) == (0x00000000, 0x00000000), (
        "Expected both reads of x0 to be 0x00000000 after a write attempt; "
        f"observed ({rs1_observed:#010x}, {rs2_observed:#010x})"
    )
