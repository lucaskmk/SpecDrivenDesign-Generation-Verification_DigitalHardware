import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the legal R-type SUB source used by this test."""
    fields = source.replace(",", " ").split()
    if len(fields) != 4 or fields[0].lower() != "sub":
        raise ValueError(f"unsupported RV32IM source: {source}")

    def register_index(token: str) -> int:
        token = token.lower()
        if not token.startswith("x"):
            raise ValueError(f"expected a register, got: {token}")
        index = int(token[1:])
        if not 0 <= index < 32:
            raise ValueError(f"register index out of range: {token}")
        return index

    rd = register_index(fields[1])
    rs1 = register_index(fields[2])
    rs2 = register_index(fields[3])

    # R-type SUB: funct7=0x20, funct3=0x0, opcode=0x33.
    return (0x20 << 25) | (rs2 << 20) | (rs1 << 15) | (rd << 7) | 0x33


@cocotb.test()
async def r_type_subtracts_operand_b_from_operand_a(dut):
    instruction = assemble_rv32im("sub x3, x1, x2")

    dut.opcode.value = (instruction >> 0) & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x00000015
    dut.operand_b.value = 0x00000006

    await Timer(1, unit="ns")

    observed = (int(dut.result.value), int(dut.branch_taken.value))
    expected = (0x0000000F, 0)
    assert observed == expected, f"expected {expected}, observed {observed}"
