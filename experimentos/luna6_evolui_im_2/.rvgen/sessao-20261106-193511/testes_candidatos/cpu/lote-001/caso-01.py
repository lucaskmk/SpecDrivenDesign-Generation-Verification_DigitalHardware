import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sb_selects_byte_width(dut):
    program = assemble_rv32im(
        "sb x0, 0(x0)\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
    assert int(dut.data_write.value) == 0, (
        f"expected data_write 0 during reset, observed {int(dut.data_write.value)}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_addr = int(dut.instr_addr.value)
    assert observed_addr == 0x00000000, (
        f"expected instr_addr 0x00000000, observed 0x{observed_addr:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected data_write 1 for SB, observed {observed_write}"
    )

    observed_width = int(dut.data_width.value)
    assert observed_width == 0x0, (
        f"expected data_width 0x0 for byte access, observed 0x{observed_width:X}"
    )
