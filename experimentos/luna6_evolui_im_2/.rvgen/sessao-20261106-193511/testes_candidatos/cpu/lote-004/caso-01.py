import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sb_x0_nonzero_s_immediate_preserves_address_bits(dut):
    program = assemble_rv32im(
        "sb x0, 5(x0)\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, observed 0x{observed_pc:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"expected instr_addr 0x00000000 after reset, observed 0x{observed_pc:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected data_write 0x1 for the SB instruction, observed 0x{observed_write:X}"
    )

    observed_addr = int(dut.data_addr.value)
    assert observed_addr == 0x00000005, (
        f"expected data_addr 0x00000005, observed 0x{observed_addr:08X}"
    )
