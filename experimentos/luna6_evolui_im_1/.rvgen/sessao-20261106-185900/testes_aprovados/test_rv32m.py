import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_rv32m_mul_smoke(dut):
    dut.operand_a.value = 0x00000007
    dut.operand_b.value = 0x00000003
    dut.funct3.value = 0x0
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x00000015, f"Expected 0x00000015, observed 0x{observed:08X}"
