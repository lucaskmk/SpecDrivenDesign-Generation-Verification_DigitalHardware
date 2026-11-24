import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def reset_sets_instruction_address(dut):
    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    dut.rst.value = 1
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, f"Expected instr_addr 0x00000000 during reset, observed 0x{observed:08X}"
