import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def reset_sets_instruction_address_to_zero(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    assert int(dut.instr_addr.value) == 0x00000000, (
        f"expected instr_addr 0x00000000 during reset, "
        f"observed 0x{int(dut.instr_addr.value):08X}"
    )
