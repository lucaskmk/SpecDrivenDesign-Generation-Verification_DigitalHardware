import cocotb
from cocotb.triggers import Timer


def model_signed_rem(a, b):
    """Reference model: signed remainder with truncation toward zero."""
    mask = 0xFFFFFFFF
    sa = a - (1 << 32) if a & 0x80000000 else a
    sb = b - (1 << 32) if b & 0x80000000 else b
    if sb == 0:
        return a & mask
    if sa == -(1 << 31) and sb == -1:
        return 0
    q = abs(sa) // abs(sb)
    if (sa < 0) != (sb < 0):
        q = -q
    r = sa - q * sb
    return r & mask


def model_signed_quot(a, b):
    """Reference model: signed quotient with truncation toward zero."""
    mask = 0xFFFFFFFF
    sa = a - (1 << 32) if a & 0x80000000 else a
    sb = b - (1 << 32) if b & 0x80000000 else b
    if sb == 0:
        return mask
    if sa == -(1 << 31) and sb == -1:
        return 0x80000000
    q = abs(sa) // abs(sb)
    if (sa < 0) != (sb < 0):
        q = -q
    return q & mask


@cocotb.test()
async def test_divider_signed_rem_selector(dut):
    """Single-factor change: want_rem 0 -> 1 on signed -7 / 2 selects the remainder."""
    operand_a = 0xFFFFFFF9  # -7
    operand_b = 0x00000002  # 2

    # Drive every input to a known value (combinational entity: no clk, no rst)
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.is_signed.value = 1
    dut.want_rem.value = 0
    await Timer(1, unit="ns")

    # Baseline: the quotient, used only as the comparison point
    quotient = model_signed_quot(operand_a, operand_b)
    assert quotient == 0xFFFFFFFD, (
        f"model quotient sanity: expected 0xFFFFFFFD, observed 0x{quotient:08X}"
    )

    # Change only want_rem
    dut.want_rem.value = 1
    await Timer(1, unit="ns")

    expected = model_signed_rem(operand_a, operand_b)
    assert expected == 0xFFFFFFFF, (
        f"model remainder sanity: expected 0xFFFFFFFF, observed 0x{expected:08X}"
    )

    observed = int(dut.result.value)
    assert observed == expected, (
        f"REM 0xFFFFFFF9 / 0x00000002: expected 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )

    # The remainder must be distinguishable from the quotient and both operands
    assert observed != quotient, (
        f"REM result must differ from quotient 0x{quotient:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != operand_a, (
        f"REM result must differ from dividend 0x{operand_a:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != operand_b, (
        f"REM result must differ from divisor 0x{operand_b:08X}, "
        f"observed 0x{observed:08X}"
    )
