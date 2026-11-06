import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the RV32M MUL source used by this test."""
    parts = source.strip().lower().replace(",", " ").split()
    if parts[:1] != ["mul"] or len(parts) != 4:
        raise ValueError(f"Unsupported RV32IM source: {source!r}")

    registers = []
    for token in parts[1:]:
        if not token.startswith("x"):
            raise ValueError(f"Expected an integer register, got {token!r}")
        register = int(token[1:])
        if not 0 <= register < 32:
            raise ValueError(f"Register out of range: {token!r}")
        registers.append(register)

    rd, rs1, rs2 = registers
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
async def legal_mul_is_recognized(dut):
    dut.instr.value = assemble_rv32im("mul x1, x2, x3")
    dut.operand_a.value = 0x00000000
    dut.operand_b.value = 0x00000000

    await Timer(1, unit="ns")

    assert int(dut.valid.value) == 1, (
        f"Expected valid = 1, observed {int(dut.valid.value)}"
    )
