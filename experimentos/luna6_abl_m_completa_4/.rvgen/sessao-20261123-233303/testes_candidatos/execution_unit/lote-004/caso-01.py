import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def beq_taken_when_operands_are_equal(dut):
    # BEQ x5, x5, target, with target at the following instruction (offset +4).
    # The execution unit receives the decoded instruction fields.
    dut.opcode.value = 0x63
    dut.funct3.value = 0x0
    dut.funct7.value = 0x0
    dut.operand_a.value = 0x0000002A
    dut.operand_b.value = 0x0000002A

    await Timer(1, unit="ns")

    observed_taken = int(dut.branch_taken.value)
    assert observed_taken == 1, (
        f"expected branch_taken 1 for equal BEQ operands, observed {observed_taken}"
    )

    observed_result = int(dut.result.value)
    assert observed_result == 0x00000000, (
        f"expected result 0x00000000 for a supported branch, "
        f"observed 0x{observed_result:08X}"
    )
