import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_sb_nonzero_offset_unmasked_data_addr(dut):
    program = assemble_rv32im(
        "sb x0, 291(x0)\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    reset_pc = int(dut.instr_addr.value)
    assert reset_pc == 0x00000000, (
        f"Expected instr_addr to be 0x00000000 during reset, got 0x{reset_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    active_pc = int(dut.instr_addr.value)
    assert active_pc == 0x00000000, (
        f"Expected instr_addr to remain 0x00000000 immediately after reset release, got 0x{active_pc:08X}"
    )

    dut.instr_data.value = program[active_pc]
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected instr_addr to hold 0x00000000 before any clock edge, got 0x{observed_pc:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"Expected data_write to be 1 for active byte-store instruction, got {observed_write}"
    )

    observed_addr = int(dut.data_addr.value)
    assert observed_addr == 0x00000123, (
        f"Expected data_addr to equal unmasked byte offset 0x00000123, got 0x{observed_addr:08X}"
    )
