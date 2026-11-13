import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_cpu_async_reset_instr_addr(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000013
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"Expected instr_addr to be 0x00000000 during asynchronous reset, got 0x{observed:08X}"
    )
