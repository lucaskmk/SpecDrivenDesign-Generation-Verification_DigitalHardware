import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_add_wraparound(dut):
    dut.operand_a.value = 0xFFFFFFFF
    dut.operand_b.value = 0x00000001
    dut.alu_op.value = 0x0

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x00000000, (
        f"expected wrapped result 0x00000000, observed 0x{observed:08X}"
    )
