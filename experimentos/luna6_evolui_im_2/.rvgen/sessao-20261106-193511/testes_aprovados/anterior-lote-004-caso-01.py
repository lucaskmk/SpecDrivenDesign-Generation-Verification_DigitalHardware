import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def sub_register_decode_test(dut):
    program = assemble_rv32i("sub x3, x1, x2")
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
    expected = (1, 0, 0, 0, 0x1, 0, 0, 0, 0x0)
    assert observed == expected, (
        f"SUB controls: expected {expected}, observed {observed}"
    )
