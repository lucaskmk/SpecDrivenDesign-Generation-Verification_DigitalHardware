import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal RV32M R-type instruction used by this test."""
    fields = source.replace(",", " ").split()
    if len(fields) != 4 or fields[0].lower() != "div":
        raise ValueError(f"Unsupported RV32IM source: {source!r}")

    def register_number(token):
        token = token.lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected integer register, got {token!r}")
        number = int(token[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"Register out of range: {token!r}")
        return number

    rd = register_number(fields[1])
    rs1 = register_number(fields[2])
    rs2 = register_number(fields[3])

    opcode = 0x33
    funct3 = 0x4
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
async def div_nonzero_nonintegral_quotient(dut):
    dut.instr.value = assemble_rv32im("div x3, x1, x2")
    dut.operand_a.value = 0x00000011
    dut.operand_b.value = 0x00000005

    await Timer(1, unit="ns")

    assert int(dut.valid.value) == 1, (
        f"Expected valid = 1, observed {int(dut.valid.value)}"
    )
    observed = int(dut.result.value)
    assert observed == 0x00000003, (
        f"Expected result 0x00000003, observed 0x{observed:08X}"
    )
