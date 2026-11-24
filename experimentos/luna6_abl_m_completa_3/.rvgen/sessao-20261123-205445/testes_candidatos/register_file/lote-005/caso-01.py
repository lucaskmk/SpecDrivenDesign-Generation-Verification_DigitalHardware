import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_async_reset_clears_written_register(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0x12345678
    dut.rd_write.value = 0

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")

    dut.rst.value = 0
    dut.rd_write.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    dut.rd_write.value = 0
    observed = int(dut.rs1_data.value)
    assert observed == 0x12345678, (
        f"Expected 0x12345678 before reset, observed 0x{observed:08X}"
    )

    # Assert reset between rising clock edges.
    dut.rst.value = 1
    await Timer(1, unit="ns")

    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"Expected 0x00000000 during asynchronous reset, observed 0x{observed:08X}"
    )
