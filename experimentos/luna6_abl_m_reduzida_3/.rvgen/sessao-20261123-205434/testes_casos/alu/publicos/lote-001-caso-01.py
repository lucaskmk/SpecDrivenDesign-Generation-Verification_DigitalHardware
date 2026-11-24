import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_register_subtraction(dut):
    program = assemble_rv32im("sub x3, x1, x2")
    dut.instr.value = program[0]
    dut.operand_a.value = 0x2468ACE1
    dut.operand_b.value = 0x13579BDF

    await Timer(1, unit="ns")

    observed_result = int(dut.result.value)
    assert observed_result == 0x11111102, (
        f"SUB expected 0x11111102, observed 0x{observed_result:08X}"
    )

    observed_branch = int(dut.branch_taken.value)
    assert observed_branch == 0, (
        f"SUB branch_taken expected 0, observed {observed_branch}"
    )
