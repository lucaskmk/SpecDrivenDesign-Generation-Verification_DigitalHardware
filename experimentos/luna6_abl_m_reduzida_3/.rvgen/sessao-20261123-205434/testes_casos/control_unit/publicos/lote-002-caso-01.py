import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_s_immediate_reconstruction(dut):
    program = assemble_rv32im("sw x19, -1389(x6)")
    dut.instr.value = program[0]

    await Timer(1, unit="ns")

    expected = 0xFFFFFA93
    observed = int(dut.imm_s.value)
    assert observed == expected, (
        f"expected imm_s 0x{expected:08X}, observed 0x{observed:08X}"
    )
