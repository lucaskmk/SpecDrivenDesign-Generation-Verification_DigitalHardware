import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1


def to_signed32(value):
    """Interpret a 32-bit pattern as a two's-complement signed integer."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def ref_mul_high(a, b, funct3):
    """Independent reference for the multiplier group (high or low word)."""
    if funct3 == 0x0:    # MUL
        product = (to_signed32(a) * to_signed32(b)) & MASK64
        return product & MASK32
    if funct3 == 0x1:    # MULH: signed x signed
        product = (to_signed32(a) * to_signed32(b)) & MASK64
        return (product >> 32) & MASK32
    if funct3 == 0x2:    # MULHSU: signed x unsigned
        product = (to_signed32(a) * (b & MASK32)) & MASK64
        return (product >> 32) & MASK32
    if funct3 == 0x3:    # MULHU: unsigned x unsigned
        product = ((a & MASK32) * (b & MASK32)) & MASK64
        return (product >> 32) & MASK32
    raise ValueError("not a multiplier funct3")


async def apply_and_read(dut, a, b, funct3):
    """Drive the inputs, wait for combinational settling, return result."""
    dut.operand_a.value = a
    dut.operand_b.value = b
    dut.funct3.value = funct3
    await Timer(1, unit="ns")
    return int(dut.result.value)


@cocotb.test()
async def test_muldiv_unit_mulh_signed_signed(dut):
    """MULH (funct3 = 0x1) on 0x80000000 x 0xFFFFFFFF reads both operands signed."""
    operand_a = 0x80000000
    operand_b = 0xFFFFFFFF

    # Initialize all inputs to known values with MULHSU selected (support step).
    mulhsu_observed = await apply_and_read(dut, operand_a, operand_b, 0x2)

    # Support reference only: MULHSU result captured on the same operands.
    mulhsu_expected = ref_mul_high(operand_a, operand_b, 0x2)
    assert mulhsu_observed == mulhsu_expected, (
        f"MULHSU support value: expected 0x{mulhsu_expected:08X}, "
        f"observed 0x{mulhsu_observed:08X}"
    )

    # Change only funct3 to MULH.
    mulh_observed = await apply_and_read(dut, operand_a, operand_b, 0x1)

    # Independent reference: (-2^31) * (-1) = +2^31, whose high word is 0.
    mulh_expected = ref_mul_high(operand_a, operand_b, 0x1)
    assert mulh_expected == 0x00000000, (
        f"Reference sanity: expected 0x00000000, got 0x{mulh_expected:08X}"
    )
    assert mulh_observed == mulh_expected, (
        f"MULH 0x80000000 x 0xFFFFFFFF: expected 0x{mulh_expected:08X}, "
        f"observed 0x{mulh_observed:08X}"
    )

    # Must differ from the MULHSU result captured as support.
    assert mulh_observed != mulhsu_observed, (
        f"MULH result must differ from MULHSU 0x{mulhsu_observed:08X}, "
        f"observed 0x{mulh_observed:08X}"
    )

    # Must differ from the MULHU and MUL results on the same operands.
    mulhu_expected = ref_mul_high(operand_a, operand_b, 0x3)
    mul_expected = ref_mul_high(operand_a, operand_b, 0x0)
    assert mulh_observed != mulhu_expected, (
        f"MULH result must differ from MULHU 0x{mulhu_expected:08X}, "
        f"observed 0x{mulh_observed:08X}"
    )
    assert mulh_observed != mul_expected, (
        f"MULH result must differ from MUL 0x{mul_expected:08X}, "
        f"observed 0x{mulh_observed:08X}"
    )
