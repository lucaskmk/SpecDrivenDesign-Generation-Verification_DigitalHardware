import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def test_addi_smoke(dut):
    dut.opcode.value = 0x13
    dut.funct3.value = 0x0
    dut.funct7.value = 0x00
    dut.operand_a.value = 0x00000013
    dut.operand_b.value = 0x00000007

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x0000001A, (
        f"expected 0x0000001A, observed 0x{observed:08X}"
    )
