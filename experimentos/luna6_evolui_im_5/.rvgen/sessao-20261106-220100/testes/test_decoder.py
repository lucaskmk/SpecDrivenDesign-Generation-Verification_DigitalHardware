import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def smoke_valid_mul_decode(dut):
    dut.instr.value = 0x02000033  # MUL x0, x0, x0
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
    expected = (1, 0, 0, 0, 0x0, 0, 0, 0, 0x0, 1)
    assert observed == expected, f"Expected {expected}, observed {observed}"
