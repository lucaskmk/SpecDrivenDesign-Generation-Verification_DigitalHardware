import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_sub_borrow_wraparound(dut):
    dut.operand_a.value = 0x00000003
    dut.operand_b.value = 0x00000005
    dut.alu_op.value = 0x1

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0xFFFFFFFE, (
        f"expected result 0xFFFFFFFE, observed 0x{observed:08X}"
    )
