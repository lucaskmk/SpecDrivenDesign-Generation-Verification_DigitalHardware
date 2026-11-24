import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_xor_result(dut):
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0xA5C36E71
    dut.opcode.value = 0x33
    dut.funct3.value = 0x4
    dut.funct7.value = 0x00

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0xB694F5AE, (
        f"Expected XOR result 0xB694F5AE, observed 0x{observed:08X}"
    )
