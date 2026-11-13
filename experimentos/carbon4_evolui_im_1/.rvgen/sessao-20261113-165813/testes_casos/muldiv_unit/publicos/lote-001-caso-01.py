import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_muldiv_unit_selector_decoding_all_ops(dut):
    """Verify combinational muldiv_op decoding across all eight RV32M operations."""
    # Pair 1: Fixed negative-MSB operands (operand_a = -2147483641, operand_b = -3)
    # chosen without zero-divisor or signed-overflow conditions so all eight
    # muldiv_op codes (0x0 through 0x7) produce mutually distinct 32-bit results.
    dut.operand_a.value = 0x80000007
    dut.operand_b.value = 0xFFFFFFFD

    pair1_expected = [
        (0x0, "MUL", 0x7FFFFFEB),
        (0x1, "MULH", 0x00000001),
        (0x2, "MULHSU", 0x80000008),
        (0x3, "MULHU", 0x80000005),
        (0x4, "DIV", 0x2AAAAAA8),
        (0x5, "DIVU", 0x00000000),
        (0x6, "REM", 0xFFFFFFFF),
        (0x7, "REMU", 0x80000007),
    ]

    pair1_observed = []
    for op_code, op_name, expected in pair1_expected:
        dut.muldiv_op.value = op_code
        await Timer(1, unit="ns")

        observed = int(dut.result.value)
        assert observed == expected, (
            f"Pair 1 {op_name} (muldiv_op=0x{op_code:X}) mismatch on "
            f"operand_a=0x80000007, operand_b=0xFFFFFFFD: "
            f"expected 0x{expected:08X}, observed 0x{observed:08X}"
        )
        pair1_observed.append(observed)

    assert len(set(pair1_observed[:4])) == 4, (
        f"Expected four distinct multiplication words across muldiv_op 0x0..0x3, "
        f"observed {[f'0x{val:08X}' for val in pair1_observed[:4]]}"
    )
    assert len(set(pair1_observed)) == 8, (
        f"Expected eight distinct words across muldiv_op 0x0..0x7, "
        f"observed {[f'0x{val:08X}' for val in pair1_observed]}"
    )

    # Pair 2: Fixed non-divisible negative-MSB dividend and positive divisor
    # (operand_a = -7, operand_b = 2) so DIV, DIVU, REM, and REMU all produce
    # non-zero, mutually distinct 32-bit words distinct from MUL.
    dut.operand_a.value = 0xFFFFFFF9
    dut.operand_b.value = 0x00000002

    pair2_expected = [
        (0x0, "MUL", 0xFFFFFFF2),
        (0x1, "MULH", 0xFFFFFFFF),
        (0x2, "MULHSU", 0xFFFFFFFF),
        (0x3, "MULHU", 0x00000001),
        (0x4, "DIV", 0xFFFFFFFD),
        (0x5, "DIVU", 0x7FFFFFFC),
        (0x6, "REM", 0xFFFFFFFF),
        (0x7, "REMU", 0x00000001),
    ]

    pair2_observed = {}
    for op_code, op_name, expected in pair2_expected:
        dut.muldiv_op.value = op_code
        await Timer(1, unit="ns")

        observed = int(dut.result.value)
        assert observed == expected, (
            f"Pair 2 {op_name} (muldiv_op=0x{op_code:X}) mismatch on "
            f"operand_a=0xFFFFFFF9, operand_b=0x00000002: "
            f"expected 0x{expected:08X}, observed 0x{observed:08X}"
        )
        pair2_observed[op_code] = observed

    div_rem_words = [
        pair2_observed[0x4],
        pair2_observed[0x5],
        pair2_observed[0x6],
        pair2_observed[0x7],
    ]
    assert len(set(div_rem_words)) == 4, (
        f"Expected four distinct division/remainder words across muldiv_op 0x4..0x7, "
        f"observed {[f'0x{val:08X}' for val in div_rem_words]}"
    )
    assert pair2_observed[0x0] not in div_rem_words, (
        f"Expected MUL result 0xFFFFFFF2 to differ from DIV/DIVU/REM/REMU results, "
        f"observed MUL=0x{pair2_observed[0x0]:08X} and div/rem={[f'0x{val:08X}' for val in div_rem_words]}"
    )
