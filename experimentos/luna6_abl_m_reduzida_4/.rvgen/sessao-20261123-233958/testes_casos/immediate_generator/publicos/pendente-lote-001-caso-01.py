import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_i_immediate_clear_sign_zero_fills_upper_bits(dut):
    dut.instr.value = 0x00700093  # addi x1, x0, 7
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    assert observed == 0x00000007, (
        f"imm_i: expected 0x00000007 with zero-filled upper bits, "
        f"observed 0x{observed:08X}"
    )
