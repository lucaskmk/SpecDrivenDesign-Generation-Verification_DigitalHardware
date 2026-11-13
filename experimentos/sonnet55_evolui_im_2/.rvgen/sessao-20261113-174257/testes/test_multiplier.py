import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_multiplier(dut):
    """Smoke test: MULHU of 0xFFFFFFFF x 0xFFFFFFFF gives 0xFFFFFFFE."""
    operand_a = 0xFFFFFFFF
    operand_b = 0xFFFFFFFF
    op = 0x3

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.op.value = op

    await Timer(1, unit="ns")

    # Independent reference: unsigned product reduced modulo 2^64, high word
    product64 = (operand_a * operand_b) & ((1 << 64) - 1)
    expected = (product64 >> 32) & 0xFFFFFFFF

    observed = int(dut.result.value)
    assert observed == expected, (
        f"MULHU 0xFFFFFFFF x 0xFFFFFFFF: expected result 0x{expected:08X}, "
        f"observed 0x{observed:08X}"
    )
