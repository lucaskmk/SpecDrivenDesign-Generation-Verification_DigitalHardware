import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def byte_store_asserts_write_enable(dut):
    program = assemble_rv32i(
        "addi x0, x0, 0\n"
        "sb x0, 0(x0)"
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.rst.value = 0
    dut.instr_data.value = program[int(dut.instr_addr.value)]
    await Timer(1, unit="ns")

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000004, (
        f"Expected sequential instr_addr 0x00000004, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.instr_data.value = program[int(dut.instr_addr.value)]
    await Timer(1, unit="ns")
    assert int(dut.data_write.value) == 1, (
        f"Expected data_write 1 for the byte-store instruction, "
        f"observed {int(dut.data_write.value)}"
    )
