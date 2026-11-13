import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def reset_suppresses_store_write(dut):
    program = assemble_rv32i(
        "sw x0, 0(x0)\n"
        "halt: jal x0, halt"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    pc = int(dut.instr_addr.value)
    assert pc == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, observed 0x{pc:08X}"
    )
    assert pc in program, f"Expected a program instruction at PC 0x{pc:08X}"
    dut.instr_data.value = program[pc]
    await Timer(1, unit="ns")

    write_enable = int(dut.data_write.value)
    assert write_enable == 0, (
        f"Expected data_write 0 during reset, observed {write_enable}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")
    write_enable = int(dut.data_write.value)
    assert write_enable == 1, (
        f"Expected the valid store to assert data_write outside reset, observed {write_enable}"
    )

    dut.rst.value = 1
    await Timer(1, unit="ns")
    pc = int(dut.instr_addr.value)
    assert pc == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, observed 0x{pc:08X}"
    )
    write_enable = int(dut.data_write.value)
    assert write_enable == 0, (
        f"Expected data_write 0 during reset with a valid store instruction, observed {write_enable}"
    )
