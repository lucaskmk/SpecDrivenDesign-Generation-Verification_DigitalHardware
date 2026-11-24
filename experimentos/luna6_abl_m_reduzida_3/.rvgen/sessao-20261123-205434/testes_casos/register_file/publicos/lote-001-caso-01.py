import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_write_to_x0_is_discarded(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x00
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0xA5C30001
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.rd_write.value = 1

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"Expected x0 readback 0x00000000 after an enabled write, "
        f"observed 0x{observed:08X}"
    )
