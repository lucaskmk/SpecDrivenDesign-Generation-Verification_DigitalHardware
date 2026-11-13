import cocotb
from cocotb.triggers import Timer


async def eval_muldiv(dut, operand_a: int, operand_b: int, muldiv_op: int) -> int:
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.muldiv_op.value = muldiv_op
    await Timer(1, unit="ns")
    return int(dut.result.value)


@cocotb.test()
async def test_signed_division_overflow_and_neighbor_exclusion(dut):
    # Initialize all declared input ports to known values.
    dut.operand_a.value = 0x00000000
    dut.operand_b.value = 0x00000001
    dut.muldiv_op.value = 0x0
    await Timer(1, unit="ns")

    # Exact signed-overflow operand pair: minimum negative 32-bit signed integer
    # (0x80000000) divided/multiplied by negative one (0xFFFFFFFF) across all 8 selectors.
    overflow_selector_expectations = [
        (0x0, "MUL", 0x80000000),
        (0x1, "MULH", 0x00000000),
        (0x2, "MULHSU", 0x80000000),
        (0x3, "MULHU", 0x7FFFFFFF),
        (0x4, "DIV", 0x80000000),
        (0x5, "DIVU", 0x00000000),
        (0x6, "REM", 0x00000000),
        (0x7, "REMU", 0x80000000),
    ]

    for op_code, op_name, expected in overflow_selector_expectations:
        observed = await eval_muldiv(dut, 0x80000000, 0xFFFFFFFF, op_code)
        assert observed == expected, (
            f"{op_name} (muldiv_op=0x{op_code:X}) on (0x80000000, 0xFFFFFFFF) mismatch: "
            f"expected 0x{expected:08X}, observed 0x{observed:08X}"
        )

    # Single-factor neighbor perturbations and swapped operand order under
    # signed quotient (0x4) and signed remainder (0x6) as differential witnesses.
    differential_witnesses = [
        # Perturb operand_a by +1: (-2^31 + 1) / -1 = +2^31 - 1 (0x7FFFFFFF), rem 0x00000000
        (0x80000001, 0xFFFFFFFF, 0x7FFFFFFF, 0x00000000, "operand_a perturbed by one"),
        # Perturb operand_b by -1: (-2^31) / -2 = +2^30 (0x40000000), rem 0x00000000
        (0x80000000, 0xFFFFFFFE, 0x40000000, 0x00000000, "operand_b perturbed by one"),
        # Swapped operands: -1 / (-2^31) = 0 (0x00000000), dividend-signed rem -1 (0xFFFFFFFF)
        (0xFFFFFFFF, 0x80000000, 0x00000000, 0xFFFFFFFF, "swapped operand order"),
    ]

    for op_a, op_b, expected_div, expected_rem, label in differential_witnesses:
        observed_div = await eval_muldiv(dut, op_a, op_b, 0x4)
        assert observed_div == expected_div, (
            f"DIV (muldiv_op=0x4) mismatch for {label} (0x{op_a:08X}, 0x{op_b:08X}): "
            f"expected 0x{expected_div:08X}, observed 0x{observed_div:08X}"
        )

        observed_rem = await eval_muldiv(dut, op_a, op_b, 0x6)
        assert observed_rem == expected_rem, (
            f"REM (muldiv_op=0x6) mismatch for {label} (0x{op_a:08X}, 0x{op_b:08X}): "
            f"expected 0x{expected_rem:08X}, observed 0x{observed_rem:08X}"
        )

    # Re-apply the exact signed-overflow pair to confirm purely combinational recovery.
    recheck_div = await eval_muldiv(dut, 0x80000000, 0xFFFFFFFF, 0x4)
    assert recheck_div == 0x80000000, (
        f"DIV (muldiv_op=0x4) recheck on (0x80000000, 0xFFFFFFFF) mismatch: "
        f"expected 0x80000000, observed 0x{recheck_div:08X}"
    )

    recheck_rem = await eval_muldiv(dut, 0x80000000, 0xFFFFFFFF, 0x6)
    assert recheck_rem == 0x00000000, (
        f"REM (muldiv_op=0x6) recheck on (0x80000000, 0xFFFFFFFF) mismatch: "
        f"expected 0x00000000, observed 0x{recheck_rem:08X}"
    )
