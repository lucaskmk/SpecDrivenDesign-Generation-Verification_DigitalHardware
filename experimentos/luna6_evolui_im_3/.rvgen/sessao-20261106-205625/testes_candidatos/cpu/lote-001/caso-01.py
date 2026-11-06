import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def jal_x0_zero_offset_keeps_fetch_address(dut):
    program = assemble_rv32im("halt: jal x0, halt")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    for completion in range(3):
        current_pc = int(dut.instr_addr.value)
        assert current_pc == 0x00000000, (
            f"Expected self-loop address 0x00000000 before completion "
            f"{completion + 1}, observed 0x{current_pc:08X}"
        )

        dut.instr_data.value = program[current_pc]
        await Timer(1, unit="ns")

        dut.clk.value = 1
        await Timer(1, unit="ns")

        observed = int(dut.instr_addr.value)
        assert observed == 0x00000000, (
            f"Expected self-loop address 0x00000000 after completion "
            f"{completion + 1}, observed 0x{observed:08X}"
        )

        dut.clk.value = 0
        await Timer(1, unit="ns")
