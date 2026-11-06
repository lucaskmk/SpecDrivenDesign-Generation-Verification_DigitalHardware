import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_fence_unsupported_opcode_defaults(dut):
    program = assemble_rv32im("fence")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    expected = (0, 0, 0, 0, 0, 0, 0, 0, 0)
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
        f"FENCE default controls: expected {expected}, observed {observed}"
    )
