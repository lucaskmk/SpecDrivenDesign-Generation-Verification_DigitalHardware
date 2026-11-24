import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_lui_top_u_immediate_bit(dut):
    # A legal LUI with the top bit of its U-immediate payload set.
    dut.instr.value = 0x800002B7
    await Timer(1, unit="ns")

    imm_u = int(dut.imm_u.value)
    assert (imm_u & 0x80000000) != 0, (
        f"imm_u[31]: expected 1, observed {(imm_u >> 31) & 1}"
    )
