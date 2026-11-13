import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mul_smoke(dut):
    dut.operand_a.value = 0x00000007
    dut.operand_b.value = 0xFFFFFFFD
    dut.funct3.value = 0x0  # MUL

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0xFFFFFFEB, (
        f"Expected 0xFFFFFFEB, observed 0x{observed:08X}"
    )
