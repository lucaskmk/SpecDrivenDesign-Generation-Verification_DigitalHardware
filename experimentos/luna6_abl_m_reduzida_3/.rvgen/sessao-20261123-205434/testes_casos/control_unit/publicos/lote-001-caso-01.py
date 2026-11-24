import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_lui_high_u_immediate_is_not_sign_extended(dut):
    program = assemble_rv32im("lui x1, 0x80000")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.imm_u.value)
    assert observed == 0x80000000, (
        f"expected imm_u 0x80000000, observed 0x{observed:08X}"
    )
    assert observed & 0x00000FFF == 0x00000000, (
        f"expected imm_u low 12 bits to be 0x00000000, "
        f"observed 0x{observed & 0x00000FFF:03X}"
    )
