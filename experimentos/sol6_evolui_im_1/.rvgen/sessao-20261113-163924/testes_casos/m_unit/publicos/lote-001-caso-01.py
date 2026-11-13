import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mulh_signed_high_half(dut):
    operand_a = 0x00000007
    operand_b = 0xFFFFFFFD

    def signed32(value):
        return value - 0x100000000 if value & 0x80000000 else value

    product = signed32(operand_a) * signed32(operand_b)
    expected_high = (product >> 32) & 0xFFFFFFFF
    mul_low = product & 0xFFFFFFFF

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x1  # MULH
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == expected_high, (
        f"MULH expected 0x{expected_high:08X}, observed 0x{observed:08X}"
    )
    assert observed != mul_low, (
        f"MULH expected a result different from MUL's 0x{mul_low:08X}, "
        f"observed 0x{observed:08X}"
    )
