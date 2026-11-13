import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def lui_selects_pass_b(dut):
    program = assemble_rv32i("lui x5, 0x12345")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.alu_control.value)
    expected = 0xA
    assert observed == expected, (
        f"LUI alu_control: expected 0x{expected:X}, observed 0x{observed:X}"
    )
