import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def non_control_instruction_advances_pc_sequentially(dut):
    program = assemble_rv32im(
        "addi x1, x0, 1\n"
        "addi x2, x0, 2"
    )

    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await Timer(2, unit="ns")
    dut.rst.value = 1
    await Timer(1, unit="ns")

    during_reset = int(dut.instr_addr.value)
    assert during_reset == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, observed 0x{during_reset:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    before_completion = int(dut.instr_addr.value)
    assert before_completion == 0x00000000, (
        f"Expected instr_addr 0x00000000 before completion, "
        f"observed 0x{before_completion:08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    after_completion = int(dut.instr_addr.value)
    assert after_completion == 0x00000004, (
        f"Expected instr_addr 0x00000004 after completion, "
        f"observed 0x{after_completion:08X}"
    )

    dut.instr_data.value = program[after_completion]
