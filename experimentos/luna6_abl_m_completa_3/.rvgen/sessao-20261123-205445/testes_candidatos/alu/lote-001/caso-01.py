import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal register-register AND instruction used by this test."""
    fields = source.replace(",", " ").split()
    if (
        len(fields) != 4
        or fields[0].lower() != "and"
        or any(not field.lower().startswith("x") for field in fields[1:])
    ):
        raise ValueError(f"unsupported RV32IM source: {source}")

    rd, rs1, rs2 = (int(field[1:]) for field in fields[1:])
    if any(register < 0 or register > 31 for register in (rd, rs1, rs2)):
        raise ValueError(f"invalid register in source: {source}")

    opcode = 0x33
    funct3 = 0x7
    funct7 = 0x00
    return (
        (funct7 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | opcode
    )


@cocotb.test()
async def register_register_and(dut):
    instruction = assemble_rv32im("and x5, x6, x7")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0xA5F00F3C
    dut.operand_b.value = 0x3CC33C5A

    await Timer(1, unit="ns")

    observed_result = int(dut.result.value)
    observed_branch_taken = int(dut.branch_taken.value)
    assert observed_result == 0x24C00C18, (
        f"expected result 0x24C00C18, observed 0x{observed_result:08X}"
    )
    assert observed_branch_taken == 0, (
        f"expected branch_taken 0x0, observed 0x{observed_branch_taken:X}"
    )
