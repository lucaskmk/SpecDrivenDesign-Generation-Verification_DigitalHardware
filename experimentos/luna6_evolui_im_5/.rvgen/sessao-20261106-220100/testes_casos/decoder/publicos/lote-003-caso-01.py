import cocotb
from cocotb.triggers import Timer
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def test_valid_store_asserts_mem_write(dut):
    program = assemble_rv32im("sw x2, 12(x1)")
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.mem_write.value)
    assert observed == 1, f"Expected mem_write=1, observed {observed}"
