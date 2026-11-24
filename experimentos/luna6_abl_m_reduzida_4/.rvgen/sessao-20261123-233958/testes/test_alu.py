import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_alu_add_smoke(dut):
    dut.operand_a.value = 0x00000002
    dut.operand_b.value = 0x00000003
    dut.alu_op.value = 0x00

    await Timer(1, unit="ns")

    assert int(dut.result.value) == 0x00000005, (
        f"expected result 0x00000005, observed 0x{int(dut.result.value):08X}"
    )
