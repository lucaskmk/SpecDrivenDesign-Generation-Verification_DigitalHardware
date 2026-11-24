import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_enabled_write_updates_nonzero_register(dut):
    address_width = min(
        len(dut.read_addr1),
        len(dut.read_addr2),
        len(dut.write_addr),
    )
    address_mask = (1 << address_width) - 1
    destination = 0x07 & address_mask
    assert destination != 0, "Expected a nonzero destination register"

    data_width = min(len(dut.write_data), len(dut.read_data1))
    data_mask = (1 << data_width) - 1
    write_value = 0xA55A3CC3 & data_mask

    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = destination
    dut.read_addr2.value = 0x00 & address_mask
    dut.write_enable.value = 0
    dut.write_addr.value = 0x00 & address_mask
    dut.write_data.value = 0x00000000 & data_mask

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start(start_high=False))

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == 0x00000000, (
        f"Expected destination to read 0x00000000 before the write, "
        f"observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    dut.write_enable.value = 1
    dut.write_addr.value = destination
    dut.write_data.value = write_value

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    observed = int(dut.read_data1.value)
    assert observed == write_value, (
        f"Expected destination to read 0x{write_value:08X} after the enabled write, "
        f"observed 0x{observed:08X}"
    )

    clock.stop()
