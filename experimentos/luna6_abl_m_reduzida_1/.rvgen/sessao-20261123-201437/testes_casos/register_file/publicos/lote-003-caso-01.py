import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_pending_write_is_not_visible_before_rising_edge(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 7
    dut.read_addr2.value = 0
    dut.write_enable.value = 0
    dut.write_addr.value = 0
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.write_enable.value = 1
    dut.write_addr.value = 7
    dut.write_data.value = 0xA5C31E7B
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0x00000000, (
        f"Expected 0x00000000 before the rising edge, observed 0x{observed:08X}"
    )
