import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def store_write_is_suppressed_during_reset(dut):
    program = assemble_rv32im("sw x1, 0(x0)")

    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    # Assert reset while the clock is low, then supply the legal store at PC 0.
    dut.rst.value = 1
    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    dut.instr_data.value = program[pc]
    await Timer(1, unit="ns")

    observed = int(dut.data_write.value)
    assert observed == 0, (
        f"Expected data_write 0 during reset for a word store, observed {observed}"
    )
