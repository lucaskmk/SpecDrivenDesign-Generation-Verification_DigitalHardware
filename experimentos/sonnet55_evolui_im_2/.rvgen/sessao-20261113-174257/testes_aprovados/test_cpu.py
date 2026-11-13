import cocotb
from cocotb.clock import Clock
from cocotb.triggers import Timer


@cocotb.test()
async def test_cpu_reset_pc(dut):
    """Smoke test: asserting reset drives instr_addr to 0x00000000 without a clock edge."""
    # Drive every input to a known value before any observation.
    dut.clk.value = 0
    dut.rst.value = 0
    dut.instr_data.value = 0x00000013  # NOP (ADDI x0, x0, 0)
    dut.data_read_data.value = 0x00000000

    # Single clock is started for the DUT; it is not relied on for the check.
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

    # Assert reset asynchronously and wait for simulation time only.
    dut.rst.value = 1
    await Timer(1, unit="ns")

    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"instr_addr during reset: expected 0x00000000, observed 0x{observed:08X}"
    )
