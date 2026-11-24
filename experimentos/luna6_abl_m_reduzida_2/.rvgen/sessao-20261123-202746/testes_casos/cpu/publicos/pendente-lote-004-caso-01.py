import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def sb_effective_address_includes_positive_s_immediate(dut):
    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000013
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    observed_pc = int(dut.instr_addr.value)
    assert observed_pc == 0x00000000, (
        f"expected instr_addr 0x00000000 after reset, observed 0x{observed_pc:08X}"
    )

    # SB x0, 12(x0): imm[4:0] = 12, rs1 = x0, rs2 = x0, funct3 = 0, opcode = 0x23.
    dut.instr_data.value = 0x00000623
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_addr = int(dut.data_addr.value)
    assert observed_addr == 0x0000000C, (
        f"expected data_addr 0x0000000C, observed 0x{observed_addr:08X}"
    )

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected data_write 1 for SB, observed {observed_write}"
    )
