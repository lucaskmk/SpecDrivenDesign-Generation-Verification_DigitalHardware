import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def mulh_signed_high_half(dut):
    dut.operand_a.value = 0xFFFFFFFF
    dut.operand_b.value = 0x80000001
    dut.funct3.value = 0x1
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    expected_signed = 0x00000000
    unsigned_high = 0x80000000

    assert observed == expected_signed, (
        f"expected signed product high half 0x{expected_signed:08X}, "
        f"observed 0x{observed:08X}"
    )
    assert observed != unsigned_high, (
        f"expected result to distinguish signed from unsigned high half "
        f"0x{unsigned_high:08X}, observed 0x{observed:08X}"
    )
