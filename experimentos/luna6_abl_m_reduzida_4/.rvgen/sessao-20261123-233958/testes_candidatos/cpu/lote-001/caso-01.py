import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def sequential_instruction_advances_pc_by_four(dut):
    # ADDI x0, x0, 0
    instruction = 0x00000013

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = instruction
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected instr_addr=0x00000000 during reset, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected instr_addr=0x00000000 before the first instruction, "
        f"observed 0x{observed:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    dut.clk.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000004, (
        f"Expected instr_addr=0x00000004 after the sequential instruction, "
        f"observed 0x{observed:08X}"
    )

    dut.instr_data.value = instruction
    await Timer(1, unit="ns")
