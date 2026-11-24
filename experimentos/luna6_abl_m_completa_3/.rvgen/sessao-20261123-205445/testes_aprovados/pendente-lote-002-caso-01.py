import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_positive_addi_has_zero_i_immediate_upper_bits(dut):
    # ADDI x1, x0, 7
    dut.instr.value = 0x00700093
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    assert observed & 0xFFFFF000 == 0x00000000, (
        f"imm_i upper bits expected 0x00000000, "
        f"observed 0x{observed & 0xFFFFF000:08X}"
    )
