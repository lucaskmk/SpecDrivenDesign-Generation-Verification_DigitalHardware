import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_disabled_write_preserves_register(dut):
    register = 0x0B
    established_value = 0x13579BDF
    disabled_payload = 0x2468ACE0

    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = register
    dut.rs2_addr.value = 0x00
    dut.rd_addr.value = register
    dut.rd_data.value = established_value
    dut.rd_write.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(1, unit="ns")
    dut.rst.value = 0

    dut.rd_write.value = 1
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == established_value, (
        f"Expected 0x{established_value:08X} after initialization, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )

    dut.rd_write.value = 0
    dut.rd_data.value = disabled_payload
    assert int(dut.rs1_data.value) == established_value, (
        f"Expected 0x{established_value:08X} before disabled write, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.rs1_data.value) == established_value, (
        f"Expected 0x{established_value:08X} after disabled write, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )
