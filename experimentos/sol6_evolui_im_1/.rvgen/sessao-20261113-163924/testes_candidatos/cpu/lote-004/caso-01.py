import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sw_exposes_word_width(dut):
    program = assemble_rv32im(
        """
        sw x0, 0(x0)
        halt: jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    # Keep the assembled instruction at the current fetch address.
    dut.instr_data.value = program[int(dut.instr_addr.value)]
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    observed_width = int(dut.data_width.value)
    assert observed_write == 1, (
        f"Expected data_write=1 for SW, observed {observed_write}"
    )
    assert observed_width == 0x2, (
        f"Expected data_width=0x2 for SW, observed 0x{observed_width:X}"
    )
