import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer


@cocotb.test()
async def valid_sw_asserts_data_write_outside_reset(dut):
    # Encoding for: sw x0, 12(x0)
    instruction = 0x00002623

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = instruction
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start()

    await Timer(2, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed = int(dut.data_write.value)
    assert observed == 1, f"Expected data_write=1 for SW outside reset, observed {observed}"
