import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF


def to_signed32(value):
    """Interpret a 32-bit value as a signed integer."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def ref_mul_low(a, b):
    """Reference MUL: low 32 bits of the exact product."""
    return ((a * b) & ((1 << 64) - 1)) & MASK32


def ref_div_signed(a, b):
    """Reference DIV with explicit truncation toward zero (b is non-zero here)."""
    sa = to_signed32(a)
    sb = to_signed32(b)
    q = abs(sa) // abs(sb)
    if (sa < 0) != (sb < 0):
        q = -q
    return q & MASK32


@cocotb.test()
async def test_muldiv_unit_divider_selection(dut):
    """funct3(2)=1 routes the divider quotient to result instead of the product."""
    a = 100
    b = 7
    funct3_mul = 0x0  # MUL
    funct3_div = 0x4  # DIV (signed quotient)

    expected_product = ref_mul_low(a, b)
    expected_quotient = ref_div_signed(a, b)

    # Sanity-check the independent reference against the plan values.
    assert expected_product == 0x000002BC, (
        f"reference product: expected 0x000002BC, got 0x{expected_product:08X}"
    )
    assert expected_quotient == 0x0000000E, (
        f"reference quotient: expected 0x0000000E, got 0x{expected_quotient:08X}"
    )

    # Support: drive known operands with the MUL selection and read the baseline.
    dut.operand_a.value = a
    dut.operand_b.value = b
    dut.funct3.value = funct3_mul
    await Timer(1, unit="ns")

    baseline = int(dut.result.value)
    assert baseline == expected_product, (
        f"MUL 100 x 7 baseline: expected 0x{expected_product:08X}, "
        f"observed 0x{baseline:08X}"
    )

    # Focal step: change only funct3 to DIV, operands unchanged.
    dut.funct3.value = funct3_div
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == expected_quotient, (
        f"DIV 100 / 7: expected 0x{expected_quotient:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != baseline, (
        f"DIV result must differ from MUL baseline 0x{baseline:08X}, "
        f"observed 0x{observed:08X}"
    )
