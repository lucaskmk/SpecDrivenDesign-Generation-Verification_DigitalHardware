import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_op_and(dut):
    # AND x3, x1, x2: opcode 0x33, funct3 0x7, funct7 0x00.
    dut.opcode.value = 0x33
    dut.funct3.value = 0x7
    dut.funct7.value = 0x00
    dut.operand_a.value = 0xA5A5F00F & 0xFFFFFFFF
    dut.operand_b.value = 0x0FF00FF0 & 0xFFFFFFFF

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    expected = 0x05A00000
    assert observed == expected, (
        f"Expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
