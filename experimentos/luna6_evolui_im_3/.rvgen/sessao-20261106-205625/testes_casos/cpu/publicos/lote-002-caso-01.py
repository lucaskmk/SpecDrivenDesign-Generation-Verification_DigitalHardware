import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def byte_store_selects_byte_width(dut):
    program = assemble_rv32im(
        """
        sb x0, 0(x0)
    halt: jal x0, halt
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    Clock(dut.clk, 10, unit="ns").start()
    await Timer(1, unit="ns")

    dut.instr_data.value = program[0x00000000]
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.data_width.value)
    assert observed == 0x0, (
        f"Expected data_width 0x0 during the byte-store instruction, "
        f"observed 0x{observed:X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.instr_data.value = program[int(dut.instr_addr.value)]
