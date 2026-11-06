import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


@cocotb.test()
async def test_write_visible_only_after_acceptance(dut):
    selected_addr = 0x0D
    requested_value = 0xA5C39E71

    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = selected_addr
    dut.read_addr2.value = 0x00
    dut.write_enable.value = 0
    dut.write_addr.value = selected_addr
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0x00000000, (
        "Expected selected register to read 0x00000000 after reset; "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await FallingEdge(dut.clk)
    await Timer(1, unit="ns")

    dut.rst.value = 0
    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0x00000000, (
        "Expected selected register to remain 0x00000000 after reset release; "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )

    dut.write_enable.value = 1
    dut.write_data.value = requested_value
    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0x00000000, (
        "Expected old value 0x00000000 before write acceptance; "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == requested_value, (
        f"Expected new value 0x{requested_value:08X} after write acceptance; "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
