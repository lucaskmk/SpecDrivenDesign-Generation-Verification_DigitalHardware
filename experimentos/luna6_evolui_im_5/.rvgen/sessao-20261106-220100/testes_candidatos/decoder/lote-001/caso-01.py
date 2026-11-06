import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sll_selects_alu_control(dut):
    program = assemble_rv32im("sll x3, x1, x2")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.alu_control.value)
    expected = 0x2
    assert observed == expected, (
        f"Expected alu_control 0x{expected:X}, observed 0x{observed:X}"
    )
