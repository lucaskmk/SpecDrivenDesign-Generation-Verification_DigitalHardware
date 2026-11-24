import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_register_register_or(dut):
    program = assemble_rv32im("or x3, x1, x2")
    dut.instr.value = program[0]
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0x2468ACE1

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x377FBFFF, (
        f"OR expected 0x377FBFFF, observed 0x{observed:08X}"
    )
    observed_branch = int(dut.branch_taken.value)
    assert observed_branch == 0, (
        f"branch_taken expected 0x0, observed 0x{observed_branch:X}"
    )
