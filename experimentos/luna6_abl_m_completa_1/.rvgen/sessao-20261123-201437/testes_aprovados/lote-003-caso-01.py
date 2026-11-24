import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def non_store_data_bus_defaults(dut):
    program = assemble_rv32im(
        "addi x1, x0, 0\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    observed_addr = int(dut.data_addr.value)
    observed_width = int(dut.data_width.value)
    observed_write_data = int(dut.data_write_data.value)

    assert observed_write == 0, (
        f"Expected data_write 0, observed {observed_write}"
    )
    assert observed_addr == 0x00000000, (
        f"Expected data_addr 0x00000000, observed 0x{observed_addr:08X}"
    )
    assert observed_width == 0x2, (
        f"Expected data_width 0x2, observed 0x{observed_width:X}"
    )
    assert observed_write_data == 0x00000000, (
        f"Expected data_write_data 0x00000000, "
        f"observed 0x{observed_write_data:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")

    next_pc = int(dut.instr_addr.value)
    dut.instr_data.value = program.get(next_pc, 0x00000000)
