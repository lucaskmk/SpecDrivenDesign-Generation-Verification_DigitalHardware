import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def xor_op_register_result(dut):
    dut.opcode.value = 0x33
    dut.funct3.value = 0x4
    dut.funct7.value = 0x00
    dut.operand_a.value = 0x12345678
    dut.operand_b.value = 0x0F0FF0F0

    await Timer(1, unit="ns")

    observed_result = int(dut.result.value)
    assert observed_result == 0x1D3BA688, (
        f"expected result 0x1D3BA688, observed 0x{observed_result:08X}"
    )

    observed_branch_taken = int(dut.branch_taken.value)
    assert observed_branch_taken == 0, (
        f"expected branch_taken 0, observed {observed_branch_taken}"
    )
