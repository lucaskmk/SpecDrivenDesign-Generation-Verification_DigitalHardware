import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_enabled_write_to_x0_is_ignored(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x00
    dut.read_addr2.value = 0x00
    dut.write_enable.value = 0
    dut.write_addr.value = 0x00
    dut.write_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))

    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.write_enable.value = 1
    dut.write_addr.value = 0x00
    dut.write_data.value = 0xA55A3CC3

    await Timer(1, unit="ns")
    observed1 = int(dut.read_data1.value)
    observed2 = int(dut.read_data2.value)
    assert observed1 == 0x00000000, (
        f"Expected read_data1 0x00000000 before the write edge, observed 0x{observed1:08X}"
    )
    assert observed2 == 0x00000000, (
        f"Expected read_data2 0x00000000 before the write edge, observed 0x{observed2:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed1 = int(dut.read_data1.value)
    observed2 = int(dut.read_data2.value)
    assert observed1 == 0x00000000, (
        f"Expected read_data1 0x00000000 after an enabled write to x0, observed 0x{observed1:08X}"
    )
    assert observed2 == 0x00000000, (
        f"Expected read_data2 0x00000000 after an enabled write to x0, observed 0x{observed2:08X}"
    )
