import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_register_register_xor_decode(dut):
    program = assemble_rv32im("xor x7, x5, x6")
    dut.instr.value = program[0]
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
        int(dut.m_enable.value),
    )
    expected = (1, 0, 0, 0, 0x5, 0, 0, 0, 0x0, 0)
    assert observed == expected, f"Expected {expected}, observed {observed}"
