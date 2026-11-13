import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_load_effective_byte_address_on_data_addr(dut):
    program = assemble_rv32im("lb x1, 291(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    pc_during_reset = int(dut.instr_addr.value)
    assert pc_during_reset == 0x00000000, (
        f"Expected instr_addr to be 0x00000000 during reset, got 0x{pc_during_reset:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    pc_after_reset = int(dut.instr_addr.value)
    assert pc_after_reset == 0x00000000, (
        f"Expected instr_addr to remain 0x00000000 after reset release, got 0x{pc_after_reset:08X}"
    )

    dut.instr_data.value = program[pc_after_reset]
    await Timer(1, unit="ns")

    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"Expected instr_addr to hold 0x00000000 while presenting load, got 0x{observed_pc:08X}"
    )

    observed_data_addr = int(dut.data_addr.value)
    assert observed_data_addr == 0x00000123, (
        f"Expected unmasked byte load address 0x00000123 on data_addr, got 0x{observed_data_addr:08X}"
    )

    observed_data_write = int(dut.data_write.value)
    assert observed_data_write == 0, (
        f"Expected data_write to remain 0 during byte-load instruction, got {observed_data_write}"
    )
