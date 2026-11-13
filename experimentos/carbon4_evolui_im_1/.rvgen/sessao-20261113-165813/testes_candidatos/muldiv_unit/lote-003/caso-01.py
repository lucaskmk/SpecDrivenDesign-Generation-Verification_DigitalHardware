import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_muldiv_unit_division_by_zero_across_all_selectors(dut):
    """Verify division-by-zero boundary handling across all eight muldiv_op selectors."""
    operand_a_cases = (
        ("non_zero_positive", 0x12345678),
        ("non_zero_negative", 0x87654321),
        ("min_signed_negative", 0x80000000),
        ("zero", 0x00000000),
    )

    mul_ops = (
        ("MUL", 0x0),
        ("MULH", 0x1),
        ("MULHSU", 0x2),
        ("MULHU", 0x3),
    )
    div_ops = (
        ("DIV", 0x4),
        ("DIVU", 0x5),
    )
    rem_ops = (
        ("REM", 0x6),
        ("REMU", 0x7),
    )

    dut.operand_a.value = 0x00000000
    dut.operand_b.value = 0x00000000
    dut.muldiv_op.value = 0x0
    await Timer(1, unit="ns")

    for class_name, op_a in operand_a_cases:
        dut.operand_a.value = op_a
        dut.operand_b.value = 0x00000000

        for mnemonic, sel in mul_ops:
            dut.muldiv_op.value = sel
            await Timer(1, unit="ns")
            observed = int(dut.result.value)
            expected = 0x00000000
            assert observed == expected, (
                f"{mnemonic} (muldiv_op=0x{sel:X}) with operand_a=0x{op_a:08X} ({class_name}) "
                f"and operand_b=0x00000000 mismatch: expected 0x{expected:08X}, "
                f"observed 0x{observed:08X}"
            )

        div_results = {}
        for mnemonic, sel in div_ops:
            dut.muldiv_op.value = sel
            await Timer(1, unit="ns")
            observed = int(dut.result.value)
            expected = 0xFFFFFFFF
            assert observed == expected, (
                f"{mnemonic} (muldiv_op=0x{sel:X}) with operand_a=0x{op_a:08X} ({class_name}) "
                f"and operand_b=0x00000000 mismatch: expected 0x{expected:08X}, "
                f"observed 0x{observed:08X}"
            )
            div_results[mnemonic] = observed

        for mnemonic, sel in rem_ops:
            dut.muldiv_op.value = sel
            await Timer(1, unit="ns")
            observed = int(dut.result.value)
            expected = op_a
            assert observed == expected, (
                f"{mnemonic} (muldiv_op=0x{sel:X}) with operand_a=0x{op_a:08X} ({class_name}) "
                f"and operand_b=0x00000000 mismatch: expected 0x{expected:08X}, "
                f"observed 0x{observed:08X}"
            )
            if op_a != 0xFFFFFFFF:
                for div_mnemonic, div_val in div_results.items():
                    assert observed != div_val, (
                        f"{mnemonic} (0x{observed:08X}) must differ from {div_mnemonic} "
                        f"(0x{div_val:08X}) when operand_a=0x{op_a:08X} != 0xFFFFFFFF"
                    )
