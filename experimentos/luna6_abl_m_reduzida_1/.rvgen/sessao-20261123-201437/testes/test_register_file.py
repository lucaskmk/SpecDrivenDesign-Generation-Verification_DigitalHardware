import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_async_reset_clears_register(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.read_addr1.value = 1
    dut.read_addr2.value = 0
    dut.write_enable.value = 0
    dut.write_addr.value = 0
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 1
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0x00000000, f"Expected 0x00000000 after reset, observed 0x{observed:08X}"
