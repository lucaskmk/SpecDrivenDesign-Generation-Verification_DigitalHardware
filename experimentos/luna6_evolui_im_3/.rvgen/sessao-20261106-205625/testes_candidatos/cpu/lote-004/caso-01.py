import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def sw_selects_word_width(dut):
    program = assemble_rv32im(
        "sw x0, 0(x0)\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    dut.instr_data.value = program[0x00000000]
    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 1, (
        f"Expected data_write 1 for SW, observed {int(dut.data_write.value)}"
    )
    assert int(dut.data_width.value) == 0x2, (
        f"Expected data_width 0x2 for word access, "
        f"observed 0x{int(dut.data_width.value):X}"
    )
