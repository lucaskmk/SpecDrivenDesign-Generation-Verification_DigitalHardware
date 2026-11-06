import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the legal RV32I OR instruction used by this test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "or":
        raise ValueError(f"Unsupported RV32I source: {source}")

    registers = []
    for name in parts[1:]:
        name = name.lower()
        if not name.startswith("x"):
            raise ValueError(f"Expected a register name, got {name}")
        register = int(name[1:])
        if not 0 <= register <= 31:
            raise ValueError(f"Register out of range: {name}")
        registers.append(register)

    rd, rs1, rs2 = registers
    opcode = 0x33
    funct3 = 0x6
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
async def test_execution_unit_op_or(dut):
    instruction = assemble_rv32i("or x5, x6, x7")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0xA5C30F0F
    dut.operand_b.value = 0x5A3C33C3

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0xFFFF3FCF, (
        f"Expected 0xFFFF3FCF, observed 0x{observed:08X}"
    )

    branch_observed = int(dut.branch_taken.value)
    assert branch_observed == 0, (
        f"Expected 0x0, observed 0x{branch_observed:X}"
    )
