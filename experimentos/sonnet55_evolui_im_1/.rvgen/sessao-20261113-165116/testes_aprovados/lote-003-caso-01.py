import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def suppress_write_for_arithmetic_immediate(dut):
    program = assemble_rv32i("addi x1, x0, 7")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        "Expected instr_addr 0x00000000 during reset"
    )

    dut.instr_data.value = program[0x00000000]
    dut.rst.value = 0
    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 0, (
        "Expected data_write 0 for a valid ADDI instruction"
    )
