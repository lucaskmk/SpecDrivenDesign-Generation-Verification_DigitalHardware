import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_divider_operand_roles_quotient_swap(dut):
    """Swapping dividend and divisor changes the quotient: 100/7 = 14, 7/100 = 0."""
    # Drive every input to a known value; selectors stay fixed in quotient mode.
    dut.is_signed.value = 0
    dut.want_rem.value = 0
    dut.operand_a.value = 100
    dut.operand_b.value = 7
    await Timer(1, unit="ns")

    first_a = 100
    first_b = 7
    first = int(dut.result.value)
    expected_first = 0x0000000E
    assert first == expected_first, (
        f"quotient 100 / 7: expected 0x{expected_first:08X}, "
        f"observed 0x{first:08X}"
    )
    assert first != first_a and first != first_b, (
        f"quotient 100 / 7 (0x{first:08X}) must differ from both operands "
        f"0x{first_a:08X} and 0x{first_b:08X}"
    )

    # Change only the operand values: exchange dividend and divisor.
    dut.operand_a.value = 7
    dut.operand_b.value = 100
    await Timer(1, unit="ns")

    second = int(dut.result.value)
    expected_second = 0x00000000
    assert second == expected_second, (
        f"quotient 7 / 100 after swap: expected 0x{expected_second:08X}, "
        f"observed 0x{second:08X}"
    )
    assert first != second, (
        f"swapped quotients must differ: first 0x{first:08X}, "
        f"second 0x{second:08X}"
    )
