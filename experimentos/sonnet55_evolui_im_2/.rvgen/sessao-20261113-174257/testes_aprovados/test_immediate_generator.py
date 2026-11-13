import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_immediate_generator_smoke(dut):
    dut.instr.value = 0x80000000
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    assert observed == 0xFFFFF800, (
        f"expected imm_i=0xFFFFF800, observed 0x{observed:08X}"
    )
