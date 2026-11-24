import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def ordinary_instruction_advances_pc_by_four(dut):
    program = assemble_rv32im(
        "addi x1, x0, 1\n"
        "addi x2, x0, 2"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected reset instr_addr 0x00000000, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    current_pc = int(dut.instr_addr.value)
    assert current_pc == 0x00000000, (
        f"Expected current instr_addr 0x00000000 before execution, "
        f"observed 0x{current_pc:08X}"
    )
    dut.instr_data.value = program[current_pc]
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")

    next_pc = int(dut.instr_addr.value)
    assert next_pc == 0x00000004, (
        f"Expected next sequential instr_addr 0x00000004, "
        f"observed 0x{next_pc:08X}"
    )

    dut.instr_data.value = program[next_pc]
    await Timer(1, unit="ns")
    settled_pc = int(dut.instr_addr.value)
    assert settled_pc == 0x00000004, (
        f"Expected instr_addr to remain 0x00000004, "
        f"observed 0x{settled_pc:08X}"
    )
