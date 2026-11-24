import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_lui_asserts_reg_write(dut):
    program = assemble_rv32im("lui x5, 0x12345")
    dut.instr.value = program[0]

    await Timer(1, unit="ns")

    observed = int(dut.reg_write.value)
    assert observed == 1, (
        f"expected reg_write 0x1 for a valid LUI, observed 0x{observed:X}"
    )
