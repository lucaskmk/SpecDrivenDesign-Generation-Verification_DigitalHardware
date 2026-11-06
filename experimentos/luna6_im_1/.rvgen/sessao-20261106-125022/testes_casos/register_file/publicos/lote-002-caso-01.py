import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_disabled_write_preserves_register(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x05
    dut.read_addr2.value = 0x05
    dut.write_enable.value = 0
    dut.write_addr.value = 0x00
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    # Initialize x5 with an enabled write as setup for the disabled-write check.
    dut.write_enable.value = 1
    dut.write_addr.value = 0x05
    dut.write_data.value = 0x13579BDF
    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x13579BDF, (
        "Expected initialized x5=0x13579BDF, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )

    # A disabled request targets the selected register with a different value.
    dut.write_enable.value = 0
    dut.write_data.value = 0x2468ACE0
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x13579BDF, (
        "Expected disabled write to preserve x5=0x13579BDF, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
    assert int(dut.read_data2.value) == 0x13579BDF, (
        "Expected read_data2 to remain 0x13579BDF, "
        f"observed 0x{int(dut.read_data2.value):08X}"
    )
