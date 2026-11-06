import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source: str) -> int:
    """Assemble the legal RV32I R-type instruction used by this test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "xor":
        raise ValueError(f"Unsupported RV32I source: {source}")

    registers = [part.lower() for part in parts[1:]]
    if any(not reg.startswith("x") or not reg[1:].isdigit() for reg in registers):
        raise ValueError(f"Invalid register in source: {source}")

    rd, rs1, rs2 = (int(reg[1:]) for reg in registers)
    if any(reg < 0 or reg > 31 for reg in (rd, rs1, rs2)):
        raise ValueError(f"Register out of range in source: {source}")

    opcode = 0x33
    funct3 = 0x4
    funct7 = 0x00
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


@cocotb.test()
async def test_register_register_xor(dut):
    instruction = assemble_rv32i("xor x3, x1, x2")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x12345678
    dut.operand_b.value = 0x00FF0F0F

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x12CB5977, (
        f"Expected 0x12CB5977, observed 0x{observed:08X}"
    )
