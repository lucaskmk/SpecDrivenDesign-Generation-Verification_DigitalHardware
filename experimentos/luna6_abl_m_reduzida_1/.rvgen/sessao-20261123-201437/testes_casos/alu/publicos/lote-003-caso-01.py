import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_compare_equal_for_identical_operands(dut):
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0x13579BDF
    dut.alu_op.value = 0x0

    await Timer(1, unit="ns")

    observed = int(dut.compare_equal.value)
    assert observed == 1, f"expected compare_equal 1, observed {observed}"
