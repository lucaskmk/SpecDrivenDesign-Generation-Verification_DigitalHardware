import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


def build_program():
    """JAL x0 at PC 0 with a forward offset of 0x1924 bytes (1609 words)."""
    # Fillers occupy words at 0x4 .. 0x1920 inclusive: 0x1920 / 4 = 1608 words.
    filler_count = 0x1920 // 4
    lines = ["jal x0, target"]
    lines.extend(["addi x0, x0, 0"] * filler_count)
    lines.append("target: jal x0, target")
    return assemble_rv32im("\n".join(lines))


async def settle(dut, program, filler):
    """Feed the ROM model from the current instr_addr and let logic settle."""
    for _ in range(2):
        await Timer(1, unit="ns")
        addr = int(dut.instr_addr.value)
        dut.instr_data.value = program.get(addr, filler)
    await Timer(1, unit="ns")


@cocotb.test()
async def test_cpu_jal_forward_redirect_commits_at_edge(dut):
    """A JAL x0 with a positive word-aligned offset redirects the next fetch to PC + imm_j."""
    program = build_program()
    filler = assemble_rv32im("addi x0, x0, 0")[0]
    expected_target = 0x00001924

    # Sanity check of the fixture: JAL at 0, target is the last word, offset is not 4.
    assert 0 in program, "program has no instruction at address 0x00000000"
    assert max(program) == expected_target, (
        f"fixture target: expected 0x{expected_target:08X}, observed 0x{max(program):08X}"
    )
    assert program[0x4] == filler, "word at 0x00000004 should be the filler instruction"

    # Drive every input to a known value; clock is held low and driven manually.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = filler
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    # Reset asserted: PC is zero. Release reset without any clock edge.
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"instr_addr in reset: expected 0x00000000, observed 0x{int(dut.instr_addr.value):08X}"
    )
    dut.rst.value = 0
    await settle(dut, program, filler)

    # Before the rising edge: fetching the JAL at address zero.
    pc_before = int(dut.instr_addr.value)
    assert pc_before == 0x00000000, (
        f"instr_addr before edge: expected 0x00000000, observed 0x{pc_before:08X}"
    )
    assert int(dut.instr_data.value) == program[0], "ROM model did not present the JAL at PC 0"
    assert int(dut.data_write.value) == 0, (
        f"data_write before edge: expected 0, observed {int(dut.data_write.value)}"
    )

    # Without a clock edge the PC must not move to the target.
    await Timer(5, unit="ns")
    pc_hold = int(dut.instr_addr.value)
    assert pc_hold == 0x00000000, (
        f"instr_addr without edge: expected 0x00000000, observed 0x{pc_hold:08X}"
    )

    # Apply exactly one rising edge.
    dut.clk.value = 1
    await Timer(1, unit="ns")
    await settle(dut, program, filler)

    pc_after = int(dut.instr_addr.value)
    assert pc_after != 0x00000004, (
        f"instr_addr after JAL edge: expected 0x{expected_target:08X}, observed PC+4 0x{pc_after:08X}"
    )
    assert pc_after == expected_target, (
        f"instr_addr after JAL edge: expected 0x{expected_target:08X}, observed 0x{pc_after:08X}"
    )
    assert int(dut.data_write.value) == 0, (
        f"data_write after edge: expected 0, observed {int(dut.data_write.value)}"
    )

    # Clock low again with no further edge: the redirect stays committed.
    dut.clk.value = 0
    await settle(dut, program, filler)
    await Timer(5, unit="ns")
    pc_final = int(dut.instr_addr.value)
    assert pc_final == expected_target, (
        f"instr_addr with clock low: expected 0x{expected_target:08X}, observed 0x{pc_final:08X}"
    )
