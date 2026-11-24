import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_register_register_and(dut):
    program = assemble_rv32im("and x3, x1, x2")
    dut.instr.value = program[0]
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0x2468ACE1

    await Timer(1, unit="ns")

    expected = 0x004088C1
    observed = int(dut.result.value)
    assert observed == expected, (
        f"AND expected 0x{expected:08X}, observed 0x{observed:08X}"
    )

    branch_observed = int(dut.branch_taken.value)
    assert branch_observed == 0, (
        f"AND branch_taken expected 0, observed {branch_observed}"
    )
