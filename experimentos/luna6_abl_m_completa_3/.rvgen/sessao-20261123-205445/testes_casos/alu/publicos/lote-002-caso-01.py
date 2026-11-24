import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal RV32IM register-register instruction used by this test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "or":
        raise ValueError(f"unsupported assembly source: {source}")

    def register_number(name):
        name = name.lower()
        if not name.startswith("x"):
            raise ValueError(f"expected an integer register, got {name}")
        number = int(name[1:])
        if not 0 <= number < 32:
            raise ValueError(f"register out of range: {name}")
        return number

    rd = register_number(parts[1])
    rs1 = register_number(parts[2])
    rs2 = register_number(parts[3])

    # Encode the legal OR R-type instruction from its assembly operands.
    return (
        (rs2 << 20)
        | (rs1 << 15)
        | (0b110 << 12)
        | (rd << 7)
        | 0b0110011
    )


@cocotb.test()
async def register_register_or(dut):
    instruction = assemble_rv32im("or x3, x1, x2")

    dut.opcode.value = (instruction >> 0) & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F

    operand_a = 0x000000F0
    operand_b = 0x0000000F
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b

    await Timer(1, unit="ns")

    expected_result = operand_a | operand_b
    observed_result = int(dut.result.value)
    observed_branch_taken = int(dut.branch_taken.value)

    assert observed_result == expected_result, (
        f"expected result 0x{expected_result:08X}, "
        f"observed 0x{observed_result:08X}"
    )
    assert observed_branch_taken == 0, (
        f"expected branch_taken 0, observed {observed_branch_taken}"
    )
