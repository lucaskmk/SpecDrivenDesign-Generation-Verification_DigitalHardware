import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def suppress_store_during_reset(dut):
    program = assemble_rv32im("sw x0, 0(x0)")
    recorded_stores = []

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    clock = Clock(dut.clk, 10, unit="ns")
    clock.start(start_high=False)

    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    dut.instr_data.value = program[pc]
    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 0, (
        f"Expected data_write 0 during reset, observed "
        f"0x{int(dut.data_write.value):X}"
    )

    await RisingEdge(dut.clk)
    if int(dut.data_write.value) == 1:
        recorded_stores.append(True)
    await Timer(1, unit="ns")

    assert int(dut.data_write.value) == 0, (
        f"Expected data_write 0 during reset, observed "
        f"0x{int(dut.data_write.value):X}"
    )
    assert recorded_stores == [], (
        f"Expected no stores recorded during reset, observed "
        f"{len(recorded_stores)}"
    )

    clock.stop()
