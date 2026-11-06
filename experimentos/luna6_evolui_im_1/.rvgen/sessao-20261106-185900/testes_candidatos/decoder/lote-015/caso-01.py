import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_xor_selects_xor_alu_operation(dut):
    program = assemble_rv32im("xor x5, x6, x7")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    expected = (1, 0, 0, 0, 0x5, 0, 0, 0, 0)
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
    )
    assert observed == expected, (
        f"XOR controls: expected {expected}, observed {observed}"
    )
