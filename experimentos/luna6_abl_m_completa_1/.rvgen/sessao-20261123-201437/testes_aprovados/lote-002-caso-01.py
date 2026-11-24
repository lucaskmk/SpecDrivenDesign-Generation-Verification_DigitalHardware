import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def jal_x0_zero_holds_fetch_address(dut):
    program = assemble_rv32im("halt: jal x0, halt")
    stop_pc = 0x00000000
    stop_instruction = program[stop_pc]

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = stop_instruction
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(1, unit="ns")

    assert int(dut.instr_addr.value) == stop_pc, (
        f"Expected reset fetch address 0x{stop_pc:08X}, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    for edge_index in range(3):
        fetch_pc = int(dut.instr_addr.value)
        assert fetch_pc == stop_pc, (
            f"Before edge {edge_index + 1}, expected fetch address "
            f"0x{stop_pc:08X}, observed 0x{fetch_pc:08X}"
        )

        dut.instr_data.value = program[fetch_pc]
        await Timer(1, unit="ns")
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        observed_pc = int(dut.instr_addr.value)
        assert observed_pc == stop_pc, (
            f"After edge {edge_index + 1}, expected JAL x0, 0 to hold "
            f"fetch address at 0x{stop_pc:08X}, observed 0x{observed_pc:08X}"
        )
