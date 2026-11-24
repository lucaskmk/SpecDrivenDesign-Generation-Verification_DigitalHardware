import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def smoke_test(dut):
    dut.instr.value = 0xFFF00000
    await Timer(1, unit="ns")
    assert int(dut.imm_i.value) == 0xFFFFFFFF, f"Expected imm_i=0xFFFFFFFF, observed 0x{int(dut.imm_i.value):08X}"
