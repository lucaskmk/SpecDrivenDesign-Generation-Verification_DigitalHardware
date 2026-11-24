import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_addi_value_used_as_load_base(dut):
    # Initialize every input before starting the clock.
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000013
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(12, unit="ns")
    dut.rst.value = 0

    # ADDI x1, x0, 0x100
    dut.instr_data.value = 0x10000093
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    # The next instruction is LW x2, 0(x1).
    dut.instr_data.value = 0x0000A103
    await Timer(1, unit="ns")

    observed = int(dut.data_addr.value)
    assert observed == 0x00000100, (
        f"expected load address 0x00000100 after ADDI, observed 0x{observed:08X}"
    )
