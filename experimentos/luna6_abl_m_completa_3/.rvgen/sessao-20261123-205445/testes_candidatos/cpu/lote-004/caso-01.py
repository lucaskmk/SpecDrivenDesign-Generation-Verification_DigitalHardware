import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def jal_x0_self_loop_holds_instruction_address(dut):
    program = assemble_rv32im("loop: jal x0, loop")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected instr_addr 0x00000000 during reset, observed 0x{observed:08X}"
    )

    dut.instr_data.value = program[0x00000000]
    dut.rst.value = 0
    await Timer(1, unit="ns")

    for completion in range(3):
        address = int(dut.instr_addr.value)
        assert address == 0x00000000, (
            f"Before completion {completion + 1}, expected instr_addr "
            f"0x00000000, observed 0x{address:08X}"
        )

        dut.instr_data.value = program[address]
        await Timer(1, unit="ns")

        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")

        address = int(dut.instr_addr.value)
        assert address == 0x00000000, (
            f"After completion {completion + 1}, expected instr_addr "
            f"0x00000000, observed 0x{address:08X}"
        )
