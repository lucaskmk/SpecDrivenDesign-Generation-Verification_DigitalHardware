import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def falling_edge_does_not_advance_pc(dut):
    program = assemble_rv32im(
        "addi x1, x0, 1\n"
        "addi x2, x0, 2"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.clk.value = 1
    await Timer(1, unit="ns")

    current_pc = int(dut.instr_addr.value)
    assert current_pc == 0x00000004, (
        f"Expected support instruction at 0x00000004, observed 0x{current_pc:08X}"
    )
    dut.instr_data.value = program[current_pc]
    await Timer(1, unit="ns")

    pc_before_falling_edge = int(dut.instr_addr.value)
    dut.clk.value = 0
    await Timer(1, unit="ns")

    pc_after_falling_edge = int(dut.instr_addr.value)
    assert pc_after_falling_edge == pc_before_falling_edge, (
        f"Expected instr_addr to remain 0x{pc_before_falling_edge:08X} "
        f"after the falling edge, observed 0x{pc_after_falling_edge:08X}"
    )
