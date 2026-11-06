import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_add_decode(dut):
    dut.instr.value = 0x002081B3
    await Timer(1, unit="ns")
    assert int(dut.alu_control.value) == 0x0, "ADD alu_control: expected 0x0"
