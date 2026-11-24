import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def smoke_test(dut):
    dut.opcode.value = 0x33
    dut.funct3.value = 0x0
    dut.funct7.value = 0x00
    dut.operand_a.value = 0x00000002
    dut.operand_b.value = 0x00000003

    await Timer(1, unit="ns")

    observed = (int(dut.result.value), int(dut.branch_taken.value))
    expected = (0x00000005, 0)
    assert observed == expected, f"expected {expected}, observed {observed}"
