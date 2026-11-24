import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_or_result(dut):
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0xA5C36E71
    dut.opcode.value = 0x33
    dut.funct3.value = 0x6
    dut.funct7.value = 0x00

    await Timer(1, unit="ns")

    expected = 0xB7D7FFFF
    observed = int(dut.result.value)
    assert observed == expected, (
        f"Expected OR result 0x{expected:08X}, observed 0x{observed:08X}"
    )
