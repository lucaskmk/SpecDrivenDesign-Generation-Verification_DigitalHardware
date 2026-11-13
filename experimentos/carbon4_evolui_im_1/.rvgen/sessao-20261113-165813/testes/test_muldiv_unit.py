import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_muldiv_unit_smoke(dut):
    dut.operand_a.value = 0x00000007
    dut.operand_b.value = 0xFFFFFFFD
    dut.muldiv_op.value = 0x0

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    expected = 0xFFFFFFEB
    assert observed == expected, (
        f"MUL result mismatch: expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
