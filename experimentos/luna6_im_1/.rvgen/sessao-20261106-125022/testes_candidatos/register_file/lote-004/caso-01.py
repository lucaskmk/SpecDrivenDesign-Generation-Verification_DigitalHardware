import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer


@cocotb.test()
async def test_async_read_address_selection(dut):
    # Initialize all inputs and reset the register file.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x0
    dut.read_addr2.value = 0x0
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0x00000000
    await Timer(1, unit="ns")

    # Seed x7 with a known nonzero value using an accepted write.
    dut.rst.value = 0
    dut.write_enable.value = 1
    dut.write_addr.value = 0x7
    dut.write_data.value = 0xA5C39E17
    await Timer(1, unit="ns")
    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    dut.write_enable.value = 0
    await Timer(1, unit="ns")

    # With the clock held low and no write accepted, select x7 on both ports.
    dut.read_addr1.value = 0x7
    dut.read_addr2.value = 0x7
    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0xA5C39E17, (
        "Expected read_data1=0xA5C39E17 for x7"
    )
    assert int(dut.read_data2.value) == 0xA5C39E17, (
        "Expected read_data2=0xA5C39E17 for x7"
    )

    # Change only read_addr1, without a clock edge or an accepted write.
    dut.read_addr1.value = 0x0
    await Timer(1, unit="ns")
    assert int(dut.read_data1.value) == 0x00000000, (
        "Expected read_data1=0x00000000 for x0 after the address change"
    )
    assert int(dut.read_data2.value) == 0xA5C39E17, (
        "Expected read_data2=0xA5C39E17 to remain selected on x7"
    )
