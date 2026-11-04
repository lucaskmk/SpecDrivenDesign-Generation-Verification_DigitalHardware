import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from rvgen.riscv_asm import assemble_rv32i


@cocotb.test()
async def byte_store_preserves_low_effective_address_bit(dut):
    program = assemble_rv32i(
        """
        addi x0, x0, 0
        sb x0, 1(x0)
        """
    )

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0
    dut.data_read_data.value = 0

    clock = Clock(dut.clk, 10, unit="ns")
    await clock.start(start_high=False)

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.instr_data.value = program[0]
    dut.rst.value = 0
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"Expected instr_addr 0x00000000 before the first rising edge, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000004, (
        f"Expected sequential instr_addr 0x00000004, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )

    dut.instr_data.value = program[4]
    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 1, (
        f"Expected data_write 1 for the byte store, "
        f"observed {int(dut.data_write.value)}"
    )
    assert int(dut.data_addr.value) == 0x00000001, (
        f"Expected unmasked data_addr 0x00000001, "
        f"observed 0x{int(dut.data_addr.value):08X}"
    )
