import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def smoke_test(dut):
    dut.instr.value = 0x00100093  # ADDI x1, x0, 1
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
    expected = (1, 0, 0, 1, 0x0, 0, 0, 0, 0x0)
    assert observed == expected, f"ADDI controls: expected {expected}, observed {observed}"
