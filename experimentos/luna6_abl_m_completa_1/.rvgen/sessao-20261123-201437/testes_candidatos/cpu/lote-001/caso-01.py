import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def ordinary_instruction_advances_pc_by_four(dut):
    program = assemble_rv32im(
        "addi x0, x0, 0\n"
        "addi x0, x0, 0"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0]
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    await FallingEdge(dut.clk)
    dut.rst.value = 0
    dut.instr_data.value = program[int(dut.instr_addr.value)]
    await Timer(1, unit="ns")

    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected starting instr_addr 0x00000000, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    next_address = int(dut.instr_addr.value)
    assert next_address == 0x00000004, (
        f"Expected instr_addr 0x00000004 after completing the instruction, "
        f"observed 0x{next_address:08X}"
    )

    dut.instr_data.value = program[next_address]
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000004, (
        f"Expected instr_addr to remain 0x00000004 after updating the fetch input, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
