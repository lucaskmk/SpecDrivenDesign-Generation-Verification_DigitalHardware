import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_cleared_values_persist_after_reset_deassertion(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.read_addr1.value = 0x1
    dut.read_addr2.value = 0x1F
    dut.write_enable.value = 0
    dut.write_addr.value = 0x0
    dut.write_data.value = 0x00000000

    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x00000000, (
        f"Expected read_data1=0x00000000 during reset, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
    assert int(dut.read_data2.value) == 0x00000000, (
        f"Expected read_data2=0x00000000 during reset, "
        f"observed 0x{int(dut.read_data2.value):08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    assert int(dut.read_data1.value) == 0x00000000, (
        f"Expected read_data1=0x00000000 after reset deassertion, "
        f"observed 0x{int(dut.read_data1.value):08X}"
    )
    assert int(dut.read_data2.value) == 0x00000000, (
        f"Expected read_data2=0x00000000 after reset deassertion, "
        f"observed 0x{int(dut.read_data2.value):08X}"
    )
