import cocotb
from cocotb.triggers import Timer


@cocotb.test()
async def mulhu_unsigned_high_product(dut):
    # Both operands have their top bits set; their unsigned high product
    # differs from the signed and mixed-signed high products.
    operand_a = 0xC0000001
    operand_b = 0xD0000003

    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.funct3.value = 0x3  # MULHU

    await Timer(1, unit="ns")

    expected = ((operand_a * operand_b) >> 32) & 0xFFFFFFFF
    observed = int(dut.result.value)
    assert observed == expected, (
        f"expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
