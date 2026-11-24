import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal SUB source instruction used by this test."""
    parts = source.replace(",", "").split()
    if len(parts) != 4 or parts[0] != "sub":
        raise ValueError(f"unsupported RV32IM source: {source}")

    def register(name):
        if not name.startswith("x"):
            raise ValueError(f"expected a register name, got {name}")
        return int(name[1:])

    rd, rs1, rs2 = (register(name) for name in parts[1:])
    if any(reg < 0 or reg > 31 for reg in (rd, rs1, rs2)):
        raise ValueError("register index out of range")

    opcode = 0x33
    funct3 = 0x0
    funct7 = 0x20
    return (
        (funct7 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | opcode
    )


@cocotb.test()
async def test_subtracts_operand_b_from_operand_a(dut):
    instruction = assemble_rv32im("sub x3, x1, x2")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x00000013
    dut.operand_b.value = 0x00000007

    await Timer(1, unit="ns")

    expected = (0x00000013 - 0x00000007) & 0xFFFFFFFF
    observed = int(dut.result.value)
    assert observed == expected, (
        f"expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
