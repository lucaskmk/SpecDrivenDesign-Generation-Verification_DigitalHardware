import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def addi_advances_sequential_fetch_address(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00700093  # addi x1, x0, 7
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, observed 0x{observed:08X}"
    )

    dut.rst.value = 0
    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000000, (
        f"expected instr_addr 0x00000000 before the instruction completes, "
        f"observed 0x{observed:08X}"
    )

    dut.clk.value = 1
    await Timer(1, unit="ns")
    observed = int(dut.instr_addr.value)
    assert observed == 0x00000004, (
        f"expected instr_addr 0x00000004 after sequential execution, "
        f"observed 0x{observed:08X}"
    )
