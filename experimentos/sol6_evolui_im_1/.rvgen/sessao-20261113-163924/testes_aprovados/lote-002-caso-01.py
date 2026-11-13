import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sh_exposes_halfword_width(dut):
    program = assemble_rv32im(
        """
        sh x0, 0(x0)
        halt: jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 20, unit="ns").start(start_high=False))
    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    dut.instr_data.value = program[pc]
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.data_width.value)
    assert observed == 0x1, (
        f"Expected data_width=0x1 during SH, observed 0x{observed:X}"
    )
