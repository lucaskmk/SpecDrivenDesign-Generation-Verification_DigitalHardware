import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_decoder_smoke(dut):
    # SUB x1, x2, x3: funct7=0x20, rs2=0x03, rs1=0x02, funct3=0x0, rd=0x01, opcode=0x33
    dut.instr.value = 0x403100B3
    await Timer(1, unit="ns")

    observed = (
        int(dut.reg_write.value),
        int(dut.mem_write.value),
        int(dut.alu_src_a_pc.value),
        int(dut.alu_src_b_imm.value),
        int(dut.alu_control.value),
        int(dut.muldiv_op.value),
        int(dut.branch_enable.value),
        int(dut.jump.value),
        int(dut.jalr.value),
        int(dut.wb_select.value),
    )
    expected = (1, 0, 0, 0, 0x1, 0x0, 0, 0, 0, 0x0)
    assert observed == expected, f"Expected {expected}, observed {observed}"
