import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_decoder_conditional_branch_class(dut):
    # Assemble a canonical conditional branch using non-zero source registers,
    # a non-zero branch target label offset, and BLT (non-BEQ) so branch-condition
    # alu_control (0x2) is distinct from default zero.
    program = assemble_rv32im(
        "blt x5, x12, target\n"
        "addi x0, x0, 0\n"
        "target: addi x0, x0, 0"
    )
    branch_instr = program[0]

    dut.instr.value = branch_instr
    await Timer(1, unit="ns")

    assert int(dut.branch_enable.value) == 1, (
        f"Expected branch_enable=1, observed {int(dut.branch_enable.value)}"
    )
    assert int(dut.alu_control.value) == 0x2, (
        f"Expected alu_control=0x2 for BLT, observed {int(dut.alu_control.value):#x}"
    )
    assert int(dut.reg_write.value) == 0, (
        f"Expected reg_write=0, observed {int(dut.reg_write.value)}"
    )
    assert int(dut.mem_write.value) == 0, (
        f"Expected mem_write=0, observed {int(dut.mem_write.value)}"
    )
    assert int(dut.alu_src_a_pc.value) == 0, (
        f"Expected alu_src_a_pc=0, observed {int(dut.alu_src_a_pc.value)}"
    )
    assert int(dut.alu_src_b_imm.value) == 0, (
        f"Expected alu_src_b_imm=0, observed {int(dut.alu_src_b_imm.value)}"
    )
    assert int(dut.muldiv_op.value) == 0x0, (
        f"Expected muldiv_op=0x0, observed {int(dut.muldiv_op.value):#x}"
    )
    assert int(dut.jump.value) == 0, (
        f"Expected jump=0, observed {int(dut.jump.value)}"
    )
    assert int(dut.jalr.value) == 0, (
        f"Expected jalr=0, observed {int(dut.jalr.value)}"
    )
    assert int(dut.wb_select.value) == 0x0, (
        f"Expected wb_select=0x0, observed {int(dut.wb_select.value):#x}"
    )
