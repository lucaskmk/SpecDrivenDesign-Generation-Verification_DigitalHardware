import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer

from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sb_exposes_byte_width(dut):
    program = assemble_rv32im("sb x0, 0(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))
    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    assert pc == 0x00000000, (
        f"Expected reset PC 0x00000000, observed 0x{pc:08X}"
    )
    dut.instr_data.value = program[pc]
    dut.rst.value = 0

    # Observe the store's combinational bus outputs before its completing edge.
    await Timer(1, unit="ns")
    write = int(dut.data_write.value)
    assert write == 1, f"Expected SB data_write=1, observed {write}"

    width = int(dut.data_width.value)
    assert width == 0x0, (
        f"Expected SB data_width=0x0, observed 0x{width:X}"
    )
