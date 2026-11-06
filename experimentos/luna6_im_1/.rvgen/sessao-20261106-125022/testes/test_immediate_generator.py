import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_immediate_generator_smoke(dut):
    dut.instr.value = 0xABCDEF12
    await Timer(1, unit="ns")
    assert int(dut.imm_i.value) == 0xFFFFFABC, (
        f"expected imm_i 0xFFFFFABC, observed 0x{int(dut.imm_i.value):08X}"
    )
