import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_alu_sub(dut):
    def reference(a, b):
        mask = 0xFFFFFFFF

        def signed32(value):
            return value if value < 0x80000000 else value - 0x100000000

        return (
            (a - b) & mask,
            int(a == b),
            int(signed32(a) < signed32(b)),
            int(a < b),
        )

    a = 0x00000002
    b = 0x00000003
    op = 0x01

    dut.operand_a.value = a
    dut.operand_b.value = b
    dut.alu_op.value = op

    await Timer(1, unit="ns")

    expected_result, expected_equal, expected_signed_less, expected_unsigned_less = (
        reference(a, b)
    )

    observed_result = int(dut.result.value)
    assert observed_result == expected_result, (
        f"expected result 0x{expected_result:08X}, "
        f"observed 0x{observed_result:08X}"
    )

    observed_equal = int(dut.equal.value)
    assert observed_equal == expected_equal, (
        f"expected equal 0x{expected_equal:X}, observed 0x{observed_equal:X}"
    )

    observed_signed_less = int(dut.signed_less.value)
    assert observed_signed_less == expected_signed_less, (
        f"expected signed_less 0x{expected_signed_less:X}, "
        f"observed 0x{observed_signed_less:X}"
    )

    observed_unsigned_less = int(dut.unsigned_less.value)
    assert observed_unsigned_less == expected_unsigned_less, (
        f"expected unsigned_less 0x{expected_unsigned_less:X}, "
        f"observed 0x{observed_unsigned_less:X}"
    )
