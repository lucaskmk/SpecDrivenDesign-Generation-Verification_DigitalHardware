import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_store_s_immediate_address(dut):
    """A word store with base x0 puts the split S immediate on data_addr, with data_write 1 and word width."""
    # S immediate 0xAC (172): instr[31:25] = 0x5 and instr[11:7] = 0xC.
    # The fields are nonzero and distinct. The value is a multiple of four.
    # A swapped-field decode would give 0x185, and a truncated one a different value.
    program = assemble_rv32im(
        "sw x0, 172(x0)\n"
        "halt: jal x0, halt\n"
    )
    store_word = program[0]

    expected_addr = 0x000000AC

    # The clock is never started, so clk stays low for the whole test.
    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    # Asynchronous reset with no clock edge.
    dut.rst.value = 1
    await Timer(1, unit="ns")
    pc_reset = int(dut.instr_addr.value)
    assert pc_reset == 0x00000000, (
        f"instr_addr during reset: expected 0x00000000, observed 0x{pc_reset:08X}"
    )
    dut.rst.value = 0
    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    assert pc == 0x00000000, (
        f"instr_addr after reset release: expected 0x00000000, observed 0x{pc:08X}"
    )

    # Present the store at the current PC and let the combinational outputs settle.
    dut.instr_data.value = store_word
    await Timer(2, unit="ns")

    addr = int(dut.data_addr.value)
    assert addr == expected_addr, (
        f"data_addr for sw x0, 172(x0): expected 0x{expected_addr:08X}, observed 0x{addr:08X}"
    )

    write = int(dut.data_write.value)
    assert write == 1, f"data_write for sw: expected 1, observed {write}"

    width = int(dut.data_width.value)
    assert width == 0x2, f"data_width for sw: expected 0x2, observed 0x{width:X}"
