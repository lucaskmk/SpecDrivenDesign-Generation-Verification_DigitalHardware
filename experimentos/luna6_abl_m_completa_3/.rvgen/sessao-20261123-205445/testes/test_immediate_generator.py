import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_immediate_generator_smoke(dut):
    dut.instr.value = 0xABC00000
    await Timer(1, unit="ns")
    assert int(dut.imm_i.value) == 0xFFFFFABC, "imm_i expected 0xFFFFFABC"
