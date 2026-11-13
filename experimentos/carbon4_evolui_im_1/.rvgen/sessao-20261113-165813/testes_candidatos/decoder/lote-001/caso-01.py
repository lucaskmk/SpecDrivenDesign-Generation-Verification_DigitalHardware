import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_load_instruction_decode(dut):
    program = assemble_rv32im("lw x7, -16(x11)")
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

    assert reg_write == 1, f"Expected reg_write=1, observed {reg_write}"
    assert mem_write == 0, f"Expected mem_write=0, observed {mem_write}"
    assert alu_src_a_pc == 0, f"Expected alu_src_a_pc=0, observed {alu_src_a_pc}"
    assert alu_src_b_imm == 1, f"Expected alu_src_b_imm=1, observed {alu_src_b_imm}"
    assert alu_control == 0x0, f"Expected alu_control=0x0, observed {alu_control:#x}"
    assert muldiv_op == 0x0, f"Expected muldiv_op=0x0, observed {muldiv_op:#x}"
    assert branch_enable == 0, f"Expected branch_enable=0, observed {branch_enable}"
    assert jump == 0, f"Expected jump=0, observed {jump}"
    assert jalr == 0, f"Expected jalr=0, observed {jalr}"
    assert wb_select == 0x1, f"Expected wb_select=0x1, observed {wb_select:#x}"
