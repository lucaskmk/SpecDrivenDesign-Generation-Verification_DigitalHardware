import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def supported_add_deasserts_branch_taken(dut):
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    dut.funct7.value = 0x00
    dut.operand_a.value = 0x00000012
    dut.operand_b.value = 0x00000034

    await Timer(1, unit="ns")

    observed = int(dut.branch_taken.value)
    assert observed == 0, f"expected branch_taken 0x0, observed 0x{observed:X}"
