import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def smoke_mul(dut):
    dut.operand_a.value = 0xFFFFFFFF
    dut.operand_b.value = 0x00000002
    dut.funct3.value = 0x0
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0xFFFFFFFE, f"expected 0xFFFFFFFE, observed 0x{observed:08X}"
