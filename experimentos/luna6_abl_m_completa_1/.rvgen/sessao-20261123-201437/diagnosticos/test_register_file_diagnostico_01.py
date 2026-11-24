import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_register_file_diagnostico_01(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x0
    dut.read_addr2.value = 0x0
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    dut.rst.value = 0
    dut.read_addr1.value = 0x1
    dut.read_addr2.value = 0x1
    dut.write_enable.value = 1
    dut.write_addr.value = 0x1
    dut.write_data.value = 0xA55A3CC3

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.write_enable.value = 0

    observed1 = int(dut.read_data1.value)
    observed2 = int(dut.read_data2.value)
    assert observed1 == 0xA55A3CC3 and observed2 == 0xA55A3CC3, (
        f"Expected both reads to be 0xA55A3CC3; "
        f"observed 0x{observed1:08X} and 0x{observed2:08X}"
    )
