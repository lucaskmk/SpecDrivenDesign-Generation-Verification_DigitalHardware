import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_mul_enables_m_writeback(dut):
    dut.instr.value = 0x02000033  # MUL x0, x0, x0
    await Timer(1, unit="ns")

    observed = int(dut.m_enable.value)
    assert observed == 1, f"Expected m_enable=1, observed {observed}"
