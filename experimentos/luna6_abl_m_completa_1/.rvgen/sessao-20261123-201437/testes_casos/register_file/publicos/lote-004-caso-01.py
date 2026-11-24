import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_disabled_write_preserves_register(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x07
    dut.read_addr2.value = 0x00
    dut.write_enable.value = 0
    dut.write_addr.value = 0x07
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 0

    # Initialize x7 with a known marker using an enabled write.
    dut.write_enable.value = 1
    dut.write_data.value = 0xA55A3CC3
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0xA55A3CC3, (
        "Expected initialized x7 to read 0xA55A3CC3"
    )

    # Present a different value while writes are disabled.
    dut.clk.value = 0
    dut.write_enable.value = 0
    dut.write_data.value = 0x5AA5C33C
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0xA55A3CC3, (
        "Expected disabled write to preserve x7 as 0xA55A3CC3"
    )
