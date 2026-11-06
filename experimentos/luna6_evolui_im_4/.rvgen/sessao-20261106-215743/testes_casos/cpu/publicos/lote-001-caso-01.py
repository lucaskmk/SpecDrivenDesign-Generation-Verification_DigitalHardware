import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def sequential_instruction_advances_fetch_address(dut):
    program = assemble_rv32i("addi x0, x0, 0")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        "Expected instr_addr 0x00000000 during reset"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        "Expected instr_addr 0x00000000 before instruction completion"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000004, (
        "Expected instr_addr 0x00000004 after sequential instruction completion"
    )
