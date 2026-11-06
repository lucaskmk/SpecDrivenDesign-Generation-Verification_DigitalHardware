import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def valid_load_selects_memory_read_writeback(dut):
    program = assemble_rv32im("lw x5, 0(x3)")
    dut.instr.value = program[0]

    await Timer(1, unit="ns")

    observed = int(dut.wb_select.value)
    assert observed == 0x1, f"Expected wb_select 0x1, observed 0x{observed:X}"
