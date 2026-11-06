import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal MUL source used by this test."""
    fields = source.replace(",", " ").split()
    if len(fields) != 4 or fields[0].lower() != "mul":
        raise ValueError(f"Unsupported RV32IM source: {source}")

    rd, rs1, rs2 = (
        int(field.lower().removeprefix("x"))
        for field in fields[1:]
    )
    if any(register < 0 or register > 31 for register in (rd, rs1, rs2)):
        raise ValueError(f"Register out of range in source: {source}")

    opcode = 0x33
    funct3 = 0x0
    funct7 = 0x01
    return (
        (funct7 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | opcode
    )


@cocotb.test()
async def mul_low_32_bit_product(dut):
    dut.instr.value = assemble_rv32im("mul x3, x1, x2")
    dut.operand_a.value = 0x00000007
    dut.operand_b.value = 0x00000009

    await Timer(1, unit="ns")

    expected = (0x00000007 * 0x00000009) & 0xFFFFFFFF
    observed_valid = int(dut.valid.value)
    observed_result = int(dut.result.value)

    assert observed_valid == 1, (
        f"Expected valid=1, observed valid={observed_valid}"
    )
    assert observed_result == expected, (
        f"Expected result 0x{expected:08X}, "
        f"observed 0x{observed_result:08X}"
    )
