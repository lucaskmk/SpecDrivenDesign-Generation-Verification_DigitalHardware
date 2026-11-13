import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_divider_is_signed_cleared_gives_unsigned_quotient(dut):
    """Clearing is_signed with fixed operand bits changes the quotient from
    signed (-7 / 2) to unsigned (4294967289 / 2)."""
    operand_a = 0xFFFFFFF9
    operand_b = 0x00000002
    signed_quotient = 0xFFFFFFFD
    unsigned_quotient = 0x7FFFFFFC

    # Drive every input to a known value (combinational entity: no clk, no rst)
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.want_rem.value = 0
    dut.is_signed.value = 1
    await Timer(1, unit="ns")

    # Signed baseline, only the comparison point for the new behavior
    baseline = int(dut.result.value)
    assert baseline == signed_quotient, (
        f"Signed baseline 0xFFFFFFF9 / 0x00000002 (is_signed=1, want_rem=0): "
        f"expected 0x{signed_quotient:08X}, observed 0x{baseline:08X}"
    )

    # Change only is_signed; operands and want_rem stay the same
    dut.is_signed.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == unsigned_quotient, (
        f"Unsigned quotient 0xFFFFFFF9 / 0x00000002 (is_signed=0, want_rem=0): "
        f"expected 0x{unsigned_quotient:08X}, observed 0x{observed:08X}"
    )
    assert observed != baseline, (
        f"Clearing is_signed must change the quotient: signed result "
        f"0x{baseline:08X}, unsigned result 0x{observed:08X}"
    )
    assert observed != operand_a and observed != operand_b, (
        f"Result 0x{observed:08X} must differ from operands "
        f"0x{operand_a:08X} and 0x{operand_b:08X}"
    )
