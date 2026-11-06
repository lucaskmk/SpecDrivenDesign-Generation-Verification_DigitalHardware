import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def byte_load_selects_byte_width(dut):
    program = assemble_rv32im("lb x5, 0(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    dut.instr_data.value = program[pc]
    dut.rst.value = 0

    await Timer(1, unit="ns")

    observed = int(dut.data_width.value)
    assert observed == 0x0, (
        f"expected data_width 0x0 for byte load, observed 0x{observed:X}"
    )
