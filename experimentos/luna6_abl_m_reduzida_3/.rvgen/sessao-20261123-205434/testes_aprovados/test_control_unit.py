import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_i_immediate_sign_extension(dut):
    dut.instr.value = 0xFED00013
    await Timer(1, unit="ns")
    assert int(dut.imm_i.value) == 0xFFFFFFED, (
        f"expected imm_i 0xFFFFFFED, observed 0x{int(dut.imm_i.value):08X}"
    )
