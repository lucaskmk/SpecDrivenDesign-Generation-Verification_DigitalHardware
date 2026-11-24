import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_add_unsigned_overflow_wraparound(dut):
    operand_a = 0xFFFFFFFF
    operand_b = 0x00000001
    alu_op = 0x00  # ADD

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.alu_op.value = alu_op

    await Timer(1, unit="ns")

    expected_result = (operand_a + operand_b) & 0xFFFFFFFF

    def as_signed_32(value):
        return value - 0x100000000 if value & 0x80000000 else value

    expected_equal = int(operand_a == operand_b)
    expected_signed_less = int(as_signed_32(operand_a) < as_signed_32(operand_b))
    expected_unsigned_less = int(operand_a < operand_b)

    observed_result = int(dut.result.value)
    observed_equal = int(dut.equal.value)
    observed_signed_less = int(dut.signed_less.value)
    observed_unsigned_less = int(dut.unsigned_less.value)

    assert observed_result == expected_result, (
        f"expected result 0x{expected_result:08X}, "
        f"observed 0x{observed_result:08X}"
    )
    assert observed_equal == expected_equal, (
        f"expected equal {expected_equal}, observed {observed_equal}"
    )
    assert observed_signed_less == expected_signed_less, (
        f"expected signed_less {expected_signed_less}, "
        f"observed {observed_signed_less}"
    )
    assert observed_unsigned_less == expected_unsigned_less, (
        f"expected unsigned_less {expected_unsigned_less}, "
        f"observed {observed_unsigned_less}"
    )
