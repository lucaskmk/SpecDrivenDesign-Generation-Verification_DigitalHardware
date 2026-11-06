import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def divu_unsigned_quotient(dut):
    dut.operand_a.value = 0x80000000
    dut.operand_b.value = 0x00000002
    dut.funct3.value = 0x5
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x40000000, (
        f"expected 0x40000000, observed 0x{observed:08X}"
    )
