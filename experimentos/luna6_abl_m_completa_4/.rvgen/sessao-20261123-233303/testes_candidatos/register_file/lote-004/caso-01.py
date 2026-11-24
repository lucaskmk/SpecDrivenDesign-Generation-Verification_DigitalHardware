import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_read_port1_async_address_selection(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x05
    dut.read_addr2.value = 0x00
    dut.write_enable.value = 1
    dut.write_addr.value = 0x05
    dut.write_data.value = 0xA5C31F72

    await Timer(1, unit="ns")

    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")

    dut.write_enable.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0xA5C31F72, (
        f"Expected read_data1=0xA5C31F72 for read_addr1=0x5, "
        f"observed 0x{observed:08X}"
    )

    dut.read_addr1.value = 0x00
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0x00000000, (
        f"Expected read_data1=0x00000000 for read_addr1=0x0 without a clock edge, "
        f"observed 0x{observed:08X}"
    )
