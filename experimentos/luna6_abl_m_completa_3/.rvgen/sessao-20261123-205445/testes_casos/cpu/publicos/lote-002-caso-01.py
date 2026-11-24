import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def non_memory_instruction_bus_defaults(dut):
    program = assemble_rv32im("addi x1, x0, 7")

    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    dut.rst.value = 1
    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    assert observed_write == 0, (
        f"Expected data_write 0, observed {observed_write}"
    )

    observed_addr = int(dut.data_addr.value)
    assert observed_addr == 0x00000000, (
        f"Expected data_addr 0x00000000, observed 0x{observed_addr:08X}"
    )

    observed_write_data = int(dut.data_write_data.value)
    assert observed_write_data == 0x00000000, (
        f"Expected data_write_data 0x00000000, "
        f"observed 0x{observed_write_data:08X}"
    )

    observed_width = int(dut.data_width.value)
    assert observed_width == 0x2, (
        f"Expected data_width 0x2, observed 0x{observed_width:X}"
    )
