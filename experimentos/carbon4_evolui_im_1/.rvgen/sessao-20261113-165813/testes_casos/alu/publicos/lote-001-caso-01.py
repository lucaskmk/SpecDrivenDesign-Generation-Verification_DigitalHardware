import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_sub_result(dut):
    dut.operand_a.value = 0x00000005
    dut.operand_b.value = 0x00000003
    dut.alu_control.value = 0x1
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x00000002, (
        f"expected result 0x00000002, observed 0x{observed:08X}"
    )
