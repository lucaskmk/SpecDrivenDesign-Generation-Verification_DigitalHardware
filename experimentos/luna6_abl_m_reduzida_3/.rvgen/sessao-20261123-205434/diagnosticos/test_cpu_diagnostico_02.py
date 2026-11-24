import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_load_effective_address(cocotb_dut):
    cocotb_dut.clk.value = 0
    cocotb_dut.rst.value = 1
    cocotb_dut.instr_data.value = 0x10000093  # addi x1, x0, 0x100
    cocotb_dut.data_read_data.value = 0x00000000

    clock = Clock(cocotb_dut.clk, 10, unit="ns")
    clock.start()
    await Timer(2, unit="ns")
    cocotb_dut.rst.value = 0

    await RisingEdge(cocotb_dut.clk)
    await Timer(1, unit="ns")

    cocotb_dut.instr_data.value = 0x0040A103  # lw x2, 4(x1)
    await Timer(1, unit="ns")

    observed = int(cocotb_dut.data_addr.value)
    assert observed == 0x00000104, (
        f"Expected load effective address 0x00000104, observed 0x{observed:08X}"
    )
