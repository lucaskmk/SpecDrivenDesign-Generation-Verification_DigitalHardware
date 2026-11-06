import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_register_register_and_selects_alu_control(dut):
    program = assemble_rv32im("and x3, x1, x2")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.alu_control.value)
    assert observed == 0x9, (
        f"AND alu_control: expected 0x9, observed 0x{observed:X}"
    )
