import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def jal_self_loop_holds_instruction_address(dut):
    program = assemble_rv32im(
        "addi x0, x0, 0\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected reset instr_addr 0x00000000, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    dut.instr_data.value = program[0x00000000]
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected initial instr_addr 0x00000000, observed 0x{observed:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000004, (
        f"Expected ordinary instruction to advance instr_addr to 0x00000004, "
        f"observed 0x{observed:08X}"
    )
    dut.clk.value = 0
    await Timer(1, unit="ns")

    dut.instr_data.value = program[0x00000004]
    await Timer(1, unit="ns")

    for edge_number in range(2):
        before = int(dut.instr_addr.value)
        assert before == 0x00000004, (
            f"Before halt-loop edge {edge_number + 1}, expected instr_addr "
            f"0x00000004, observed 0x{before:08X}"
        )

        dut.clk.value = 1
        await Timer(1, unit="ns")

        after = int(dut.instr_addr.value)
        assert after == 0x00000004, (
            f"After halt-loop edge {edge_number + 1}, expected instr_addr "
            f"to remain 0x00000004, observed 0x{after:08X}"
        )

        dut.clk.value = 0
        await Timer(1, unit="ns")
