import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_selects_register_second_operand(dut):
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    await Timer(1, unit="ns")

    observed = int(dut.alu_b_imm.value)
    assert observed == 0, f"Expected alu_b_imm=0 for OP, observed {observed}"
