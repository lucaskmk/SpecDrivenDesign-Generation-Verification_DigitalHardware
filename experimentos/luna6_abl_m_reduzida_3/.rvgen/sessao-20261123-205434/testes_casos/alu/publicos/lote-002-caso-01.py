import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_register_xor(dut):
    program = assemble_rv32im("xor x3, x1, x2")
    dut.instr.value = program[0]
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0x2468ACE1

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x373F373E, (
        f"XOR expected 0x373F373E, observed 0x{observed:08X}"
    )
    observed_branch = int(dut.branch_taken.value)
    assert observed_branch == 0, (
        f"branch_taken expected 0, observed {observed_branch}"
    )
