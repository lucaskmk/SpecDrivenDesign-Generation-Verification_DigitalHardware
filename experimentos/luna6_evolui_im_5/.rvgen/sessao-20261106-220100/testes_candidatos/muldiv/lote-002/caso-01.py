import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mulhsu_high_half(dut):
    operand_a = 0xFFFFFFFF
    operand_b = 0x80000001

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x2
    await Timer(1, unit="ns")

    signed_a = operand_a - (1 << 32)
    unsigned_b = operand_b
    expected = ((signed_a * unsigned_b) >> 32) & 0xFFFFFFFF

    signed_b = operand_b - (1 << 32)
    witnessed_mulh = ((signed_a * signed_b) >> 32) & 0xFFFFFFFF

    observed = int(dut.result.value)
    assert observed == expected, (
        f"expected MULHSU result 0x{expected:08X}, observed 0x{observed:08X}"
    )
    assert observed != witnessed_mulh, (
        f"expected MULHSU result to differ from MULH result "
        f"0x{witnessed_mulh:08X}, observed 0x{observed:08X}"
    )
