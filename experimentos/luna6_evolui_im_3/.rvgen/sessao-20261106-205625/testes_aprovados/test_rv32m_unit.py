import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def div_by_zero_smoke(dut):
    dut.instr.value = 0x02004033
    dut.operand_a.value = 0x00000005
    dut.operand_b.value = 0x00000000

    await Timer(1, unit="ns")

    assert int(dut.result.value) == 0xFFFFFFFF, (
        f"Expected 0xFFFFFFFF, observed 0x{int(dut.result.value):08X}"
    )
