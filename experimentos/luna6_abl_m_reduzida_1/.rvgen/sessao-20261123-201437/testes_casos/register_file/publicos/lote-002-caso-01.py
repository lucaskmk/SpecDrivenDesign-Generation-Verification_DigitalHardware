import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


@cocotb.test()
async def test_synchronous_write_to_nonzero_register(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 7
    dut.read_addr2.value = 0
    dut.write_enable.value = 0
    dut.write_addr.value = 0
    dut.write_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    dut.rst.value = 0

    await FallingEdge(dut.clk)
    dut.write_enable.value = 1
    dut.write_addr.value = 7
    dut.write_data.value = 0xA5C39E71

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0xA5C39E71, (
        f"Expected 0xA5C39E71 in register 7, observed 0x{observed:08X}"
    )
