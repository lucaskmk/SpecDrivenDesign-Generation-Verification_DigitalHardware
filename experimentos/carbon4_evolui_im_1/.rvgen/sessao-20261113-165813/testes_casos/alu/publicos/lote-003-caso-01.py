import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_equal_flag_bitwise_equality(dut):
    dut.operand_a.value = 0xA55A3CC3
    dut.operand_b.value = 0xA55A3CC3
    dut.alu_control.value = 0x0
    await Timer(1, unit="ns")

    observed = int(dut.equal.value)
    assert observed == 1, f"expected equal 1 for identical operands, observed {observed}"

    dut.operand_a.value = 0xA55A3CC2
    await Timer(1, unit="ns")

    observed = int(dut.equal.value)
    assert observed == 0, f"expected equal 0 for operands differing by one bit, observed {observed}"
