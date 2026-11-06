import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def byte_load_address_preserves_low_bits(dut):
    program = assemble_rv32im("lb x0, 3(x0)")

    dut.clk.value = 0
    dut.rst.value = 1
    dut.instr_data.value = 0x00000000
    dut.data_read_data.value = 0x00000000

    await Timer(1, unit="ns")
    dut.rst.value = 0
    await Timer(1, unit="ns")

    pc = int(dut.instr_addr.value)
    dut.instr_data.value = program[pc]
    await Timer(1, unit="ns")

    observed = int(dut.data_addr.value)
    assert observed == 0x00000003, (
        f"expected data_addr 0x00000003, observed 0x{observed:08X}"
    )
