import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_enables_register_write(dut):
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    await Timer(1, unit="ns")
    assert int(dut.rd_write.value) == 1, f"Expected rd_write=1, observed {int(dut.rd_write.value)}"
