import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer


@cocotb.test()
async def test_enabled_write_updates_nonzero_register_synchronously(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.rs1_addr.value = 0x05
    dut.rs2_addr.value = 0x06
    dut.rd_addr.value = 0x05
    dut.rd_data.value = 0xA5C37E19
    dut.rd_write.value = 0

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    dut.rd_write.value = 1
    await Timer(1, unit="ns")

    assert int(dut.rs1_data.value) == 0x00000000, (
        f"Expected prior value 0x00000000 before the write edge, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )
    assert int(dut.rs2_data.value) == 0x00000000, (
        f"Expected other register value 0x00000000 before the write edge, "
        f"observed 0x{int(dut.rs2_data.value):08X}"
    )

    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start(start_high=False))
    await RisingEdge(dut.clk)
    await Timer(1, unit="ns")

    assert int(dut.rs1_data.value) == 0xA5C37E19, (
        f"Expected written value 0xA5C37E19 after the write edge, "
        f"observed 0x{int(dut.rs1_data.value):08X}"
    )
    assert int(dut.rs2_data.value) == 0x00000000, (
        f"Expected other register value 0x00000000 after the write edge, "
        f"observed 0x{int(dut.rs2_data.value):08X}"
    )
