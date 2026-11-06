import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_and_result(dut):
    dut.operand_a.value = 0xA55A3CC3
    dut.operand_b.value = 0x3C969669
    dut.alu_control.value = 0x2
    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x24121441, (
        f"expected result 0x24121441, observed 0x{observed:08X}"
    )
