import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_cpu_lb_negative_imm_sign_extended_data_addr(dut):
    program = assemble_rv32im("lb x1, -5(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    dut.rst.value = 0
    await Timer(1, unit="ns")

    fetch_addr = int(dut.instr_addr.value)
    assert fetch_addr == 0x00000000, (
        f"Expected instr_addr to remain 0x00000000 after reset release, got 0x{fetch_addr:08X}"
    )

    dut.instr_data.value = program[fetch_addr]
    await Timer(1, unit="ns")

    observed_instr_addr = int(dut.instr_addr.value)
    assert observed_instr_addr == 0x00000000, (
        f"Expected instr_addr to stay at 0x00000000 while presenting byte-load, got 0x{observed_instr_addr:08X}"
    )

    expected_data_addr = 0xFFFFFFFB
    observed_data_addr = int(dut.data_addr.value)
    assert observed_data_addr == expected_data_addr, (
        f"Expected sign-extended unmasked data_addr 0x{expected_data_addr:08X}, got 0x{observed_data_addr:08X}"
    )

    observed_data_width = int(dut.data_width.value)
    assert observed_data_width == 0x0, (
        f"Expected data_width 0x0 for byte-load instruction, got 0x{observed_data_width:X}"
    )

    observed_data_write = int(dut.data_write.value)
    assert observed_data_write == 0, (
        f"Expected data_write to be 0 for byte-load instruction, got {observed_data_write}"
    )
