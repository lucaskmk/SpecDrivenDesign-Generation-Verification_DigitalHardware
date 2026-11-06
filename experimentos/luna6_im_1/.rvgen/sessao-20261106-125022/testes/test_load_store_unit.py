import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_address_passthrough(dut):
    dut.instr.value = 0x00002003
    dut.effective_address.value = 0x1234567B
    dut.store_data_in.value = 0xA1B2C3D4
    dut.data_read_data.value = 0xD3A5C67E

    await Timer(1, unit="ns")

    assert int(dut.data_addr.value) == 0x1234567B, (
        f"expected data_addr 0x1234567B, observed 0x{int(dut.data_addr.value):08X}"
    )
