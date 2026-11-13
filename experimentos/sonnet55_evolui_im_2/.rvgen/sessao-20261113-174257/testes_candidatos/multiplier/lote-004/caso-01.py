import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1


def _interpret(value, signed):
    """Interpret a 32-bit pattern as signed or unsigned integer."""
    if signed and (value & 0x80000000):
        return value - (1 << 32)
    return value


def _reference(a, b, op):
    """Independent arbitrary-precision reference for the multiplier."""
    a_signed = op in (0, 1, 2)
    b_signed = op in (0, 1)
    product = _interpret(a, a_signed) * _interpret(b, b_signed)
    p64 = product & MASK64
    if op == 0:
        return p64 & MASK32
    return (p64 >> 32) & MASK32


@cocotb.test()
async def test_multiplier_result_slicing_mixed_pair(dut):
    """MUL returns P64[31:0]; MULH/MULHSU/MULHU return P64[63:32] for a mixed pair."""
    operand_a = 0x12345678
    operand_b = 0x9ABCDEF1

    names = {0x0: "MUL", 0x1: "MULH", 0x2: "MULHSU", 0x3: "MULHU"}

    # Drive known values on all inputs before any observation
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.op.value = 0x0
    await Timer(1, unit="ns")

    # Sanity check of the stimulus: low and high words of the unsigned
    # product are both nonzero and different
    unsigned_p64 = (operand_a * operand_b) & MASK64
    low_word = unsigned_p64 & MASK32
    high_word = (unsigned_p64 >> 32) & MASK32
    assert low_word != 0 and high_word != 0 and low_word != high_word, (
        f"stimulus pair must have distinct nonzero words: "
        f"low 0x{low_word:08X}, high 0x{high_word:08X}"
    )

    observed_by_op = {}
    for op in (0x0, 0x1, 0x2, 0x3):
        dut.operand_a.value = operand_a
        dut.operand_b.value = operand_b
        dut.op.value = op
        await Timer(1, unit="ns")

        expected = _reference(operand_a, operand_b, op)
        observed = int(dut.result.value)
        observed_by_op[op] = observed
        assert observed == expected, (
            f"{names[op]} 0x{operand_a:08X} x 0x{operand_b:08X} (op=0x{op:X}): "
            f"expected result 0x{expected:08X}, observed 0x{observed:08X}"
        )

    # The low word must not be confused with the high word
    assert observed_by_op[0x0] != observed_by_op[0x3], (
        f"MUL result 0x{observed_by_op[0x0]:08X} must differ from "
        f"MULHU result 0x{observed_by_op[0x3]:08X} for this pair"
    )
