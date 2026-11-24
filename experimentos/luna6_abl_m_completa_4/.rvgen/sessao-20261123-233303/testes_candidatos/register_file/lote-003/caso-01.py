import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer


@cocotb.test()
async def test_nonzero_register_write_commits_on_rising_edge(dut):
    destination = 0x07
    write_value = 0xA5C31F79

    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = destination
    dut.read_addr2.value = destination
    dut.write_enable.value = 0
    dut.write_addr.value = 0x00
    dut.write_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x00000000, (
        f"Expected read_data1=0x00000000 after reset, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
    assert int(dut.read_data2.value) == 0x00000000, (
        f"Expected read_data2=0x00000000 after reset, "
        f"observed 0x{int(dut.read_data2.value):08X}"
    )

    await FallingEdge(dut.clk)
    dut.write_enable.value = 1
    dut.write_addr.value = destination
    dut.write_data.value = write_value
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x00000000, (
        f"Before the rising edge, expected read_data1=0x00000000, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
    assert int(dut.read_data2.value) == 0x00000000, (
        f"Before the rising edge, expected read_data2=0x00000000, "
        f"observed 0x{int(dut.read_data2.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == write_value, (
        f"After the rising edge, expected read_data1=0x{write_value:08X}, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
    assert int(dut.read_data2.value) == write_value, (
        f"After the rising edge, expected read_data2=0x{write_value:08X}, "
        f"observed 0x{int(dut.read_data2.value):08X}"
    )
