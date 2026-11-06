import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def op_add_register_decode(dut):
    program = assemble_rv32i("add x3, x1, x2")
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
    )
    expected = (1, 0, 0, 0, 0x0, 0, 0, 0, 0x0)
    assert observed == expected, (
        f"ADD controls: expected {expected}, observed {observed}"
    )
