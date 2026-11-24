import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_addi_then_load_effective_address(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    await Timer(2, unit="ns")

    dut.rst.value = 0
    dut.instr_data.value = 0x10000093  # addi x1, x0, 0x100
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    dut.instr_data.value = 0x0000A103  # lw x2, 0(x1)
    await Timer(1, unit="ns")

    observed = int(dut.data_addr.value)
    assert observed == 0x00000100, (
        f"Expected load address 0x00000100, observed 0x{observed:08X}"
    )
