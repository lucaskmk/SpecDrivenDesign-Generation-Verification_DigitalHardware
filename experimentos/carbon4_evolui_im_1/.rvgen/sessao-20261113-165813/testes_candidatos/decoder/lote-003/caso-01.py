import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_rv32m_div_decode(dut):
    program = assemble_rv32im("div x5, x6, x7")
    dut.instr.value = program[0x00000000]
    await Timer(1, unit="ns")

    reg_write = int(dut.reg_write.value)
    mem_write = int(dut.mem_write.value)
    alu_src_a_pc = int(dut.alu_src_a_pc.value)
    alu_src_b_imm = int(dut.alu_src_b_imm.value)
    alu_control = int(dut.alu_control.value)
    muldiv_op = int(dut.muldiv_op.value)
    branch_enable = int(dut.branch_enable.value)
    jump = int(dut.jump.value)
    jalr = int(dut.jalr.value)
    wb_select = int(dut.wb_select.value)

    assert reg_write == 1, f"reg_write: expected 1, observed {reg_write}"
    assert mem_write == 0, f"mem_write: expected 0, observed {mem_write}"
    assert alu_src_a_pc == 0, f"alu_src_a_pc: expected 0, observed {alu_src_a_pc}"
    assert alu_src_b_imm == 0, f"alu_src_b_imm: expected 0, observed {alu_src_b_imm}"
    assert alu_control == 0x0, f"alu_control: expected 0x0, observed {alu_control:#x}"
    assert muldiv_op == 0x4, f"muldiv_op: expected 0x4, observed {muldiv_op:#x}"
    assert branch_enable == 0, f"branch_enable: expected 0, observed {branch_enable}"
    assert jump == 0, f"jump: expected 0, observed {jump}"
    assert jalr == 0, f"jalr: expected 0, observed {jalr}"
    assert wb_select == 0x3, f"wb_select: expected 0x3, observed {wb_select:#x}"
