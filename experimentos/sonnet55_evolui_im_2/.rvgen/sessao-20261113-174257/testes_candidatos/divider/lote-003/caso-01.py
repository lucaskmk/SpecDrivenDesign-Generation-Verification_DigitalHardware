import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_divider_remu_unsigned_remainder(dut):
    """REMU: with is_signed=0 and want_rem=1, 0xFFFFFFF9 rem 2 gives 1."""
    operand_a = 0xFFFFFFF9  # bit 31 set: large positive magnitude when unsigned
    operand_b = 0x00000002

    # Drive every input to a known defined value (no clock, no reset).
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.is_signed.value = 0
    dut.want_rem.value = 0
    await Timer(1, unit="ns")

    # Baseline (comparison point only): unsigned quotient.
    unsigned_quotient_expected = 0x7FFFFFFC
    unsigned_quotient = int(dut.result.value)
    assert unsigned_quotient == unsigned_quotient_expected, (
        f"DIVU baseline 0xFFFFFFF9 / 0x00000002: expected "
        f"0x{unsigned_quotient_expected:08X}, observed 0x{unsigned_quotient:08X}"
    )

    # Change only want_rem to select the remainder in unsigned mode.
    dut.want_rem.value = 1
    await Timer(1, unit="ns")

    expected = 0x00000001
    observed = int(dut.result.value)
    assert observed == expected, (
        f"REMU 0xFFFFFFF9 % 0x00000002: expected 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )

    signed_remainder = 0xFFFFFFFF
    assert observed != unsigned_quotient_expected, (
        f"REMU result must differ from unsigned quotient "
        f"0x{unsigned_quotient_expected:08X}, observed 0x{observed:08X}"
    )
    assert observed != signed_remainder, (
        f"REMU result must differ from signed remainder "
        f"0x{signed_remainder:08X}, observed 0x{observed:08X}"
    )
    assert observed != operand_a, (
        f"REMU result must differ from operand_a 0x{operand_a:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != operand_b, (
        f"REMU result must differ from operand_b 0x{operand_b:08X}, "
        f"observed 0x{observed:08X}"
    )
