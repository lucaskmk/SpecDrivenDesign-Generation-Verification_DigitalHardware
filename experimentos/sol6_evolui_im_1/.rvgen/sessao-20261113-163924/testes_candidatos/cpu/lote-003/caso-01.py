import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_sb_exposes_unmasked_byte_address(dut):
    program = assemble_rv32im("sb x0, 5(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = program[0x00000000]
    dut.data_read_data.value = 0x00000000
    await Timer(1, unit="ns")

    dut.instr_data.value = program[int(dut.instr_addr.value)]
    dut.rst.value = 0
    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    observed_addr = int(dut.data_addr.value)

    assert observed_write == 1, (
        f"Expected data_write=1 for SB, observed {observed_write}"
    )
    assert observed_addr == 0x00000005, (
        f"Expected unmasked data_addr=0x00000005, "
        f"observed 0x{observed_addr:08X}"
    )
