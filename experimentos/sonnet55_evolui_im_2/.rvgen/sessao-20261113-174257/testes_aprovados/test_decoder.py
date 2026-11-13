import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_decoder_smoke(dut):
    """Smoke test: MUL x5, x6, x7 must decode to the M tuple."""
    # MUL x5, x6, x7: funct7=0x01, rs2=7, rs1=6, funct3=0x0, rd=5, opcode=0x33
    dut.instr.value = 0x027302B3
    await Timer(1, unit="ns")

    observed = (
        int(dut.reg_write.value),
        int(dut.mem_write.value),
        int(dut.alu_src_a_pc.value),
        int(dut.alu_src_b_imm.value),
        int(dut.alu_control.value),
        int(dut.branch_enable.value),
        int(dut.jump.value),
        int(dut.jalr.value),
        int(dut.wb_select.value),
        int(dut.muldiv_op.value),
    )
    # M tuple: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control,
    # branch_enable, jump, jalr, wb_select, muldiv_op
    expected = (1, 0, 0, 0, 0x0, 0, 0, 0, 0x0, 1)

    assert observed == expected, (
        f"MUL decode mismatch: expected {expected} "
        f"(reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, "
        f"branch_enable, jump, jalr, wb_select, muldiv_op), observed {observed}"
    )
