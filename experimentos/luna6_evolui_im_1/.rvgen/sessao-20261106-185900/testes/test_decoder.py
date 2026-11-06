import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_decoder_add(dut):
    dut.instr.value = 0x003100B3
    await Timer(1, unit="ns")

    expected = (1, 0, 0, 0, 0, 0, 0, 0, 0)
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
    assert observed == expected, f"ADD controls: expected {expected}, observed {observed}"
