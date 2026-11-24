import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def non_store_instruction_deasserts_data_write(dut):
    program = assemble_rv32im("addi x1, x0, 1")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    dut.instr_data.value = program[pc]
    await Timer(1, unit="ns")

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.data_write.value)
    assert observed == 0, f"Expected data_write 0, observed {observed}"
