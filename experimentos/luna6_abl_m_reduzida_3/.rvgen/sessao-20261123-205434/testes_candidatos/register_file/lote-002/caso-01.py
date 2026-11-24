import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_write_nonzero_register_and_read_back(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x01
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = 0x00
    dut.rd_data.value = 0x00000000
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(1, unit="ns")
    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"After reset, expected x1 to read 0x00000000, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    dut.rd_addr.value = 0x01
    dut.rd_data.value = 0x13579BDF
    dut.rd_write.value = 1

    await Timer(1, unit="ns")
    observed = int(dut.rs1_data.value)
    assert observed == 0x00000000, (
        f"Before the write edge, expected x1 to remain 0x00000000, observed 0x{observed:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.rs1_data.value)
    assert observed == 0x13579BDF, (
        f"After the accepted write, expected x1 to read 0x13579BDF, observed 0x{observed:08X}"
    )
