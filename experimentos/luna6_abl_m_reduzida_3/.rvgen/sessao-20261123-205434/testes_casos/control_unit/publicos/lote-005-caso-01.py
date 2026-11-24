import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_b_immediate_reconstruction(dut):
    program = assemble_rv32im("beq x13, x22, -2670")
    instruction = program[0]

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    immediate = (
        (((instruction >> 31) & 0x1) << 12)
        | (((instruction >> 7) & 0x1) << 11)
        | (((instruction >> 25) & 0x3F) << 5)
        | (((instruction >> 8) & 0xF) << 1)
    )
    expected = immediate | (0xFFFFE000 if immediate & 0x1000 else 0)
    observed = int(dut.imm_b.value)

    assert observed == expected, (
        f"expected imm_b 0x{expected:08X}, observed 0x{observed:08X}"
    )
    assert observed & 0x1 == 0, (
        f"expected imm_b bit 0 to be 0, observed 0x{observed:08X}"
    )
