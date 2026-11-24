import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_alu_sub_ordinary_positive_operands(dut):
    dut.operand_a.value = 0x00000015
    dut.operand_b.value = 0x00000006
    dut.alu_op.value = 0x1

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x0000000F, (
        f"expected result 0x0000000F, observed 0x{observed:08X}"
    )
