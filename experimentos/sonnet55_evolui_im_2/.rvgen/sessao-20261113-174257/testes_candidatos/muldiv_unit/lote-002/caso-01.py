import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1


def to_signed32(value):
    """Interpret a 32-bit pattern as a two's-complement signed integer."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def ref_mulhsu(a, b):
    """Independent reference: signed operand_a times unsigned operand_b, high word."""
    product = to_signed32(a) * (b & MASK32)
    return ((product & MASK64) >> 32) & MASK32


def ref_mulhu(a, b):
    """Independent reference: unsigned x unsigned, high word."""
    product = (a & MASK32) * (b & MASK32)
    return ((product & MASK64) >> 32) & MASK32


def ref_mulh(a, b):
    """Independent reference: signed x signed, high word."""
    product = to_signed32(a) * to_signed32(b)
    return ((product & MASK64) >> 32) & MASK32


@cocotb.test()
async def test_muldiv_unit_mulhsu_signed_a_unsigned_b(dut):
    """MULHSU (funct3 = 0x2) on 0x80000000 x 0xFFFFFFFF gives 0x80000000."""
    operand_a = 0x80000000
    operand_b = 0xFFFFFFFF

    # Drive all inputs with known 0/1 values (no clock or reset exists).
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x3  # MULHU baseline (support only)
    await Timer(1, unit="ns")

    baseline = int(dut.result.value)
    baseline_expected = ref_mulhu(operand_a, operand_b)

    # Change only funct3 to select MULHSU.
    dut.funct3.value = 0x2
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    expected = ref_mulhsu(operand_a, operand_b)

    assert observed == expected, (
        f"MULHSU 0x{operand_a:08X} x 0x{operand_b:08X}: "
        f"expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
    assert observed != baseline, (
        f"MULHSU result must differ from MULHU result on identical operands: "
        f"MULHSU observed 0x{observed:08X}, MULHU observed 0x{baseline:08X} "
        f"(MULHU reference 0x{baseline_expected:08X})"
    )

    # Optional: MULHSU must also differ from the MULH reference value.
    mulh_reference = ref_mulh(operand_a, operand_b)
    assert observed != mulh_reference, (
        f"MULHSU result 0x{observed:08X} must differ from the MULH "
        f"reference value 0x{mulh_reference:08X} on identical operands"
    )
