import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def lui_unsupported_opcode_defaults(dut):
    # Encoding of lui x5, 0x12345: 0x123452B7.
    instruction = 0x123452B7

    dut.opcode.value = (instruction >> 0) & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0x2468ACE0

    await Timer(1, unit="ns")

    observed_result = int(dut.result.value)
    observed_branch_taken = int(dut.branch_taken.value)
    assert observed_result == 0x00000000, (
        f"expected result 0x00000000, observed 0x{observed_result:08X}"
    )
    assert observed_branch_taken == 0, (
        f"expected branch_taken 0, observed {observed_branch_taken}"
    )
