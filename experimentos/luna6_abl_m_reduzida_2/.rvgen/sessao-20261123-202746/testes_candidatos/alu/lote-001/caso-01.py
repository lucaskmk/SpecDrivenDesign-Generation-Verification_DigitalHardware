import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_alu_sub_result(dut):
    operand_a = 0xA5C36E71
    operand_b = 0x13579BDF

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    dut.funct7.value = 0x20

    await Timer(1, unit="ns")

    expected = (operand_a - operand_b) & 0xFFFFFFFF
    observed = int(dut.result.value)
    assert observed == expected, (
        f"Expected SUB result 0x{expected:08X}, observed 0x{observed:08X}"
    )
