import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_divu_unsigned_quotient(dut):
    dividend = 0xFFFFFFFD
    divisor = 0x80000000

    dut.operand_a.value = dividend
    dut.operand_b.value = divisor
    dut.funct3.value = 0x5  # DIVU

    await Timer(1, unit="ns")

    expected = dividend // divisor
    assert dividend % divisor != 0

    signed_dividend = dividend - 0x100000000
    signed_divisor = divisor - 0x100000000
    signed_magnitude = abs(signed_dividend) // abs(signed_divisor)
    signed_quotient = (
        -signed_magnitude
        if (signed_dividend < 0) != (signed_divisor < 0)
        else signed_magnitude
    )

    observed = int(dut.result.value)
    assert observed == expected, (
        f"Expected unsigned quotient 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != (signed_quotient & 0xFFFFFFFF), (
        f"Expected result to differ from signed quotient "
        f"0x{signed_quotient & 0xFFFFFFFF:08X}, observed 0x{observed:08X}"
    )
