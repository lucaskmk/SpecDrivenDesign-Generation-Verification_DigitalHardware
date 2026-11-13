import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_branch_immediate_sign_extension(dut):
    dut.instr.value = 0x80000000
    await Timer(1, unit="ns")

    observed = int(dut.imm_b.value)
    assert observed == 0xFFFFF000, (
        f"imm_b: expected 0xFFFFF000, observed 0x{observed:08X}"
    )
