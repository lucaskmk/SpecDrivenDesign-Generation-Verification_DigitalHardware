import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_add_smoke(dut):
    dut.instr.value = 0x00000033
    dut.operand_a.value = 0x13579BDF
    dut.operand_b.value = 0x2468ACE1

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x37C048C0, f"ADD expected 0x37C048C0, observed 0x{observed:08X}"
