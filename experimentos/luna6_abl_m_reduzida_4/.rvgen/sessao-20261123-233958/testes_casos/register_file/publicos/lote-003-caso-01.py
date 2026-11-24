import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_disabled_write_preserves_selected_register(dut):
    destination = 0x07
    stored_value = 0x13579BDF
    rejected_value = 0x2468ACE0

    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = destination
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = destination
    dut.rd_data.value = stored_value
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(1, unit="ns")
    dut.rst.value = 0

    # Establish a known value using an enabled write.
    dut.rd_write.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed_before = int(dut.rs1_data.value)
    assert observed_before == stored_value, (
        f"Expected setup value 0x{stored_value:08X}, "
        f"observed 0x{observed_before:08X}"
    )

    # Present a different value while writing is disabled.
    dut.rd_data.value = rejected_value
    dut.rd_write.value = 0
    await Timer(1, unit="ns")

    observed_before_disabled_edge = int(dut.rs1_data.value)
    assert observed_before_disabled_edge == stored_value, (
        f"Expected 0x{stored_value:08X} before the disabled-write edge, "
        f"observed 0x{observed_before_disabled_edge:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed_after = int(dut.rs1_data.value)
    assert observed_after == stored_value, (
        f"Expected disabled write to preserve 0x{stored_value:08X}, "
        f"observed 0x{observed_after:08X}"
    )
