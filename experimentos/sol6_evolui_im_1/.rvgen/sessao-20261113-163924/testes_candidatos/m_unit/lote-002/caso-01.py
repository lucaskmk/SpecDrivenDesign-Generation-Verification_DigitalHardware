import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mulhsu_mixed_signedness_high_product(dut):
    operand_a = 0x00000007
    operand_b = 0xFFFFFFFD

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x2  # MULHSU

    await Timer(1, unit="ns")

    expected = ((operand_a * operand_b) >> 32) & 0xFFFFFFFF
    signed_b = operand_b - (1 << 32)
    signed_high = ((operand_a * signed_b) >> 32) & 0xFFFFFFFF
    observed = int(dut.result.value)

    assert observed == expected, (
        f"MULHSU expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
    assert observed != signed_high, (
        f"MULHSU must differ from signed-by-signed high half "
        f"0x{signed_high:08X}; observed 0x{observed:08X}"
    )
