import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mulhu_unsigned_high_half(dut):
    operand_a = 0xC0000001
    operand_b = 0xA0000003
    expected = ((operand_a * operand_b) >> 32) & 0xFFFFFFFF

    signed_a = operand_a - 0x100000000
    signed_first_high = ((signed_a * operand_b) >> 32) & 0xFFFFFFFF
    assert expected != signed_first_high

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x3  # MULHU

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == expected, (
        f"MULHU expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
