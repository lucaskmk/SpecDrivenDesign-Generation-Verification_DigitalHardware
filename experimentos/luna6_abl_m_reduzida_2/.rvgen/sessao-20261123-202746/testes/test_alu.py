import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_alu_add_smoke(dut):
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0xA5C36E71
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    dut.funct7.value = 0x00

    await Timer(1, unit="ns")

    assert int(dut.result.value) == 0xB91B0A50, "Expected ADD result 0xB91B0A50"
