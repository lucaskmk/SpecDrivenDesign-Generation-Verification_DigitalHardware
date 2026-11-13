import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_addi_result_committed_and_stored(dut):
    """ADDI writes a distinctive value to x5; a later SW of x5 exposes it on data_write_data."""
    program = assemble_rv32im(
        "addi x5, x0, 1443\n"
        "sw x5, 8(x0)\n"
        "halt: jal x0, halt\n"
    )
    halt_word = program[8]

    def fetch(pc):
        # ROM model: answer with the instruction at the fetched address.
        return program.get(pc, halt_word)

    expected_value = 0x000005A3  # ADDI result: 0x000 + 1443

    # Drive every input to a known value before any observation.
    # The clock is driven manually so each rising edge is fully deterministic.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = fetch(0)
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    # Release reset without a clock edge; execution starts from address 0.
    dut.rst.value = 0
    await Timer(1, unit="ns")

    pc_before = int(dut.instr_addr.value)
    assert pc_before == 0x00000000, (
        f"instr_addr before ADDI edge: expected 0x00000000, observed 0x{pc_before:08X}"
    )
    dut.instr_data.value = fetch(pc_before)
    await Timer(1, unit="ns")

    # Rising edge: ADDI commits its result into x5 and the PC advances.
    dut.clk.value = 1
    await Timer(1, unit="ns")

    pc_after = int(dut.instr_addr.value)
    assert pc_after == 0x00000004, (
        f"instr_addr after ADDI edge: expected 0x00000004, observed 0x{pc_after:08X}"
    )

    # Present the store at the new PC and let the combinational logic settle.
    dut.instr_data.value = fetch(pc_after)
    dut.clk.value = 0
    await Timer(2, unit="ns")

    write_flag = int(dut.data_write.value)
    assert write_flag == 1, (
        f"data_write during SW: expected 1, observed {write_flag}"
    )

    observed = int(dut.data_write_data.value)
    assert observed == expected_value, (
        f"data_write_data during SW: expected 0x{expected_value:08X}, "
        f"observed 0x{observed:08X}"
    )
