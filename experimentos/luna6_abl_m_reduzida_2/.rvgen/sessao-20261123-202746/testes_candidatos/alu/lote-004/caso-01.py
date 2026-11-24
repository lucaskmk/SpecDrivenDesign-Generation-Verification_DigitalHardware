import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_and_returns_bitwise_intersection(dut):
    dut.operand_a.value = 0xA5C36E71
    dut.operand_b.value = 0x13579BDF
    dut.opcode.value = 0x33
    dut.funct3.value = 0x7
    dut.funct7.value = 0x00

    await Timer(1, unit="ns")

    assert int(dut.result.value) == 0x01430A51, (
        "Expected OP AND result 0x01430A51"
    )
