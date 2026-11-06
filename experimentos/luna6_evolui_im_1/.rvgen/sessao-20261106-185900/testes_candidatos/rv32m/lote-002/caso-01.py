import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mulhu_unsigned_high_word(dut):
    operand_a = 0x80000000
    operand_b = 0x00000002

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x3
    await Timer(1, unit="ns")

    expected = ((operand_a * operand_b) >> 32) & 0xFFFFFFFF
    observed = int(dut.result.value)
    assert observed == expected, (
        f"Expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
