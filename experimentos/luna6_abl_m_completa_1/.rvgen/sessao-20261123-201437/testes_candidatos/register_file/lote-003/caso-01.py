import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_async_read_updates_after_address_change(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x00
    dut.read_addr2.value = 0x00
    dut.write_enable.value = 0
    dut.write_addr.value = 0x00
    dut.write_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    # Reset and initialize x7 with a known value.
    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.write_enable.value = 1
    dut.write_addr.value = 0x07
    dut.write_data.value = 0xA55A3CC3
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    # Select x7 after the write, without waiting for another clock edge.
    dut.write_enable.value = 0
    dut.read_addr1.value = 0x07
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0xA55A3CC3, (
        f"Expected asynchronous read of x7 to be 0xA55A3CC3, "
        f"observed 0x{observed:08X}"
    )
