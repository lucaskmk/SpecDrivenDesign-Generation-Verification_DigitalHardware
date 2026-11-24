import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def smoke_test(dut):
    dut.instr.value = 0x00000037  # LUI
    await Timer(1, unit="ns")
    assert int(dut.reg_write.value) == 1, f"Expected reg_write=1, observed {dut.reg_write.value}"
