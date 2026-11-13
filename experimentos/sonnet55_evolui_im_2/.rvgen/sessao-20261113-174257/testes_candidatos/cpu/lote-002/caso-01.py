import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_load_word_i_immediate_address(dut):
    """A word load from base x0 drives data_addr with the I-immediate, width word, write 0."""
    # Legal source: one word load, base x0, positive word-aligned I-immediate
    # 1752 (0x6D8), with distinct bit groups in the immediate.
    program = assemble_rv32im(
        "lw x5, 1752(x0)\n"
        "halt: jal x0, halt\n"
    )

    expected_addr = 0x000006D8
    expected_width = 0x2

    # Drive every input to a known value; no clock edge is applied (clk held low).
    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0xA5C31E87

    await Timer(1, unit="ns")

    # Apply and release asynchronous reset, with no clock edge.
    dut.rst.value = 1
    await Timer(1, unit="ns")
    reset_pc = int(dut.instr_addr.value)
    assert reset_pc == 0x00000000, (
        f"instr_addr during reset: expected 0x00000000, observed 0x{reset_pc:08X}"
    )
    dut.rst.value = 0
    await Timer(1, unit="ns")

    # Fetch the instruction for the current PC and present it.
    pc = int(dut.instr_addr.value)
    assert pc == 0x00000000, (
        f"instr_addr after reset release: expected 0x00000000, observed 0x{pc:08X}"
    )
    dut.instr_data.value = program[pc]
    dut.data_read_data.value = 0xA5C31E87

    # Let the combinational outputs settle (no clock edge).
    await Timer(2, unit="ns")

    observed_addr = int(dut.data_addr.value)
    assert observed_addr == expected_addr, (
        f"data_addr for LW x0+1752: expected 0x{expected_addr:08X}, "
        f"observed 0x{observed_addr:08X}"
    )

    observed_width = int(dut.data_width.value)
    assert observed_width == expected_width, (
        f"data_width for LW: expected 0x{expected_width:X}, "
        f"observed 0x{observed_width:X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 0, (
        f"data_write for LW: expected 0, observed {observed_write}"
    )

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"instr_addr before any clock edge: expected 0x00000000, "
        f"observed 0x{observed_pc:08X}"
    )
