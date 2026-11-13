import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1


def to_signed32(value):
    """Interpret a 32-bit integer as a two's-complement signed value."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def ref_multiplier(op, a, b):
    """Independent reference for the multiplier group (op = funct3[1:0])."""
    if op == 0:      # MUL
        product = to_signed32(a) * to_signed32(b)
        return (product & MASK64) & MASK32
    if op == 1:      # MULH
        product = to_signed32(a) * to_signed32(b)
    elif op == 2:    # MULHSU
        product = to_signed32(a) * (b & MASK32)
    else:            # MULHU
        product = (a & MASK32) * (b & MASK32)
    return ((product & MASK64) >> 32) & MASK32


@cocotb.test()
async def test_muldiv_unit_mul_low_word(dut):
    """MUL (funct3 = 0x0) returns the low product word, not the MULHU high word."""
    operand_a = 0x80000000
    operand_b = 0xFFFFFFFF

    # Baseline (smoke) configuration: MULHU on the same operands.
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x3
    await Timer(1, unit="ns")

    mulhu_expected = ref_multiplier(3, operand_a, operand_b)
    assert mulhu_expected == 0x7FFFFFFF, (
        f"Reference sanity: expected MULHU 0x7FFFFFFF, "
        f"reference gave 0x{mulhu_expected:08X}"
    )
    mulhu_observed = int(dut.result.value)
    assert mulhu_observed == mulhu_expected, (
        f"MULHU baseline: expected 0x{mulhu_expected:08X}, "
        f"observed 0x{mulhu_observed:08X}"
    )

    # Change only funct3 to the MUL encoding; operands stay identical.
    dut.funct3.value = 0x0
    await Timer(1, unit="ns")

    expected = ref_multiplier(0, operand_a, operand_b)
    assert expected == 0x80000000, (
        f"Reference sanity: expected MUL 0x80000000, "
        f"reference gave 0x{expected:08X}"
    )
    observed = int(dut.result.value)
    assert observed == expected, (
        f"MUL 0x80000000 x 0xFFFFFFFF: expected 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != mulhu_observed, (
        f"MUL result 0x{observed:08X} must differ from the MULHU result "
        f"0x{mulhu_observed:08X} on identical operands"
    )
