import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_xor_result(dut):
    dut.operand_a.value = 0xA55AA55A
    dut.operand_b.value = 0x3CC33CC3
    dut.alu_op.value = 0x05

    await Timer(1, unit="ns")

    expected = 0x99999999
    observed = int(dut.result.value)
    assert observed == expected, (
        f"expected result 0x{expected:08X}, observed 0x{observed:08X}"
    )
