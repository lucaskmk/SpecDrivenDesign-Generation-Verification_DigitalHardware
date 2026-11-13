import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_word_store_data_width_encoding(dut):
    program = assemble_rv32im("sw x0, 0(x0)\nhalt: jal x0, halt")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    initial_pc = int(dut.instr_addr.value)
    assert initial_pc == 0x00000000, (
        f"Expected initial instr_addr 0x00000000 under reset, got 0x{initial_pc:08X}"
    )

    dut.instr_data.value = program[initial_pc]
    dut.rst.value = 0

    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected instr_addr to remain 0x00000000 after releasing reset, got 0x{observed_pc:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"Expected data_write to be 1 for word store outside reset, got {observed_write}"
    )

    observed_width = int(dut.data_width.value)
    assert observed_width == 0x2, (
        f"Expected data_width 0x2 for word store instruction, got 0x{observed_width:X}"
    )
