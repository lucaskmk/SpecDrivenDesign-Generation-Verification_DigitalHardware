import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def addi_with_x0_destination_asserts_reg_write(dut):
    program = assemble_rv32i("addi x0, x1, 7")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.reg_write.value)
    assert observed == 1, (
        f"ADDI with rd=x0: expected reg_write=1, observed reg_write={observed}"
    )
