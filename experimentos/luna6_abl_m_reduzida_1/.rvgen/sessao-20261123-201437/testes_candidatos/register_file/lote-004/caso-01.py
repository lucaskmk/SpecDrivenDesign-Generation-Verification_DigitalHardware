import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_disabled_write_preserves_register(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 7
    dut.read_addr2.value = 0
    dut.write_enable.value = 0
    dut.write_addr.value = 0
    dut.write_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(1, unit="ns")
    dut.rst.value = 0

    # Initialize x7 through the public write interface.
    dut.write_enable.value = 1
    dut.write_addr.value = 7
    dut.write_data.value = 0x13579BDF
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    initialized = int(dut.read_data1.value)
    assert initialized == 0x13579BDF, (
        f"Expected x7 to contain 0x13579BDF, observed 0x{initialized:08X}"
    )

    # Request a different value with writes disabled.
    dut.write_enable.value = 0
    dut.write_data.value = 0x2468ACE0
    await Timer(1, unit="ns")

    before_edge = int(dut.read_data1.value)
    assert before_edge == 0x13579BDF, (
        f"Expected x7 to remain 0x13579BDF before the edge, "
        f"observed 0x{before_edge:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    after_edge = int(dut.read_data1.value)
    assert after_edge == 0x13579BDF, (
        f"Expected x7 to remain 0x13579BDF after the disabled write, "
        f"observed 0x{after_edge:08X}"
    )
