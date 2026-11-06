import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mul_returns_low_word_with_distinct_nonzero_high_word(dut):
    operand_a = 0xFFFFFFFF
    operand_b = 0xFFFFFFFF
    product = operand_a * operand_b
    expected = product & 0xFFFFFFFF
    high_word = (product >> 32) & 0xFFFFFFFF

    assert high_word != 0 and high_word != expected, (
        f"Test setup requires a nonzero high word distinct from the low word; "
        f"high=0x{high_word:08X}, low=0x{expected:08X}"
    )

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x0
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == expected, (
        f"Expected MUL low word 0x{expected:08X}, observed 0x{observed:08X}"
    )
