import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_alu_or(dut):
    operand_a = 0xA55AA55A
    operand_b = 0x3CC33CC3
    alu_op = 0x08

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.alu_op.value = alu_op

    await Timer(1, unit="ns")

    expected_result = operand_a | operand_b
    expected_equal = int(operand_a == operand_b)
    signed_a = operand_a if operand_a < 0x80000000 else operand_a - 0x100000000
    signed_b = operand_b if operand_b < 0x80000000 else operand_b - 0x100000000
    expected_signed_less = int(signed_a < signed_b)
    expected_unsigned_less = int(operand_a < operand_b)

    observed_result = int(dut.result.value)
    observed_equal = int(dut.equal.value)
    observed_signed_less = int(dut.signed_less.value)
    observed_unsigned_less = int(dut.unsigned_less.value)

    assert observed_result == expected_result, (
        f"expected result 0x{expected_result:08X}, observed 0x{observed_result:08X}"
    )
    assert observed_equal == expected_equal, (
        f"expected equal 0x{expected_equal:X}, observed 0x{observed_equal:X}"
    )
    assert observed_signed_less == expected_signed_less, (
        f"expected signed_less 0x{expected_signed_less:X}, "
        f"observed 0x{observed_signed_less:X}"
    )
    assert observed_unsigned_less == expected_unsigned_less, (
        f"expected unsigned_less 0x{expected_unsigned_less:X}, "
        f"observed 0x{observed_unsigned_less:X}"
    )
