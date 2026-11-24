import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_immediate_gen_smoke(dut):
    dut.instr.value = 0xFFF00000
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    assert observed == 0xFFFFFFFF, f"imm_i: expected 0xFFFFFFFF, observed 0x{observed:08X}"
