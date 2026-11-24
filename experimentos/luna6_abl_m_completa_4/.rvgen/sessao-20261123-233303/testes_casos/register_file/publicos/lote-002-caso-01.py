import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_enabled_write_to_x0_is_ignored(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x0
    dut.read_addr2.value = 0x0
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.write_enable.value = 1
    dut.write_addr.value = 0x0
    dut.write_data.value = 0xA5C37E19

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0x00000000, (
        f"Expected read_data1=0x00000000 after an enabled write to x0, "
        f"observed 0x{observed:08X}"
    )
