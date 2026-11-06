import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_sub_result(dut):
    # Drive the legal OP SUB selector fields and unequal, nonzero operands.
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    dut.funct7.value = 0x20
    dut.operand_a.value = 0x00000019
    dut.operand_b.value = 0x00000007

    await Timer(1, unit="ns")

    observed_result = int(dut.result.value)
    assert observed_result == 0x00000012, (
        f"Expected result 0x00000012, observed 0x{observed_result:08X}"
    )

    observed_branch = int(dut.branch_taken.value)
    assert observed_branch == 0, (
        f"Expected branch_taken 0, observed {observed_branch}"
    )
