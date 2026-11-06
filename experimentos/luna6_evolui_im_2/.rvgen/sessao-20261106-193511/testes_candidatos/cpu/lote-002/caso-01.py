import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sh_asserts_halfword_store_width(dut):
    program = assemble_rv32im(
        "sh x0, 0(x0)\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, observed 0x{observed_pc:08X}"
    )
    observed_write = int(dut.data_write.value)
    assert observed_write == 0, (
        f"expected data_write 0 during reset, observed {observed_write}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"expected instr_addr 0x00000000 after reset, observed 0x{observed_pc:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected data_write 1 for SH, observed {observed_write}"
    )
    observed_width = int(dut.data_width.value)
    assert observed_width == 0x1, (
        f"expected data_width 0x1 for SH, observed 0x{observed_width:X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000004, (
        f"expected instr_addr 0x00000004 after SH, observed 0x{observed_pc:08X}"
    )
