import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer


@cocotb.test()
async def non_memory_instruction_drives_zero_data_address(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000013
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(1, unit="ns")
    dut.rst.value = 0

    # addi x1, x0, 7
    dut.instr_data.value = 0x00700093
    await Timer(1, unit="ns")

    observed = int(dut.data_addr.value)
    assert observed == 0x00000000, (
        f"Expected data_addr=0x00000000, observed 0x{observed:08X}"
    )
