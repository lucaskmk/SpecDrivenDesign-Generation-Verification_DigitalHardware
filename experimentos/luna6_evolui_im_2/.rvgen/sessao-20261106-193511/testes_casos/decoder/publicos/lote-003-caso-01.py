import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_auipc_selects_pc_as_alu_operand_a(dut):
    program = assemble_rv32im("auipc x5, 74565")
    dut.instr.value = program[0]

    await Timer(1, unit="ns")

    assert int(dut.alu_src_a_pc.value) == 1, (
        "AUIPC alu_src_a_pc: expected 0x1"
    )
