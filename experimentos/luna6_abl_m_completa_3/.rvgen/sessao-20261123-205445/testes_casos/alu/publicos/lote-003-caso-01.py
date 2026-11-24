import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal XOR register-register instruction used by this test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 4 or parts[0].lower() != "xor":
        raise ValueError(f"unsupported assembly source: {source}")

    registers = []
    for token in parts[1:]:
        token = token.lower()
        if not token.startswith("x") or not token[1:].isdigit():
            raise ValueError(f"invalid register: {token}")
        register = int(token[1:])
        if not 0 <= register <= 31:
            raise ValueError(f"register out of range: {token}")
        registers.append(register)

    rd, rs1, rs2 = registers
    opcode = 0x33
    funct3 = 0x4
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
async def register_register_xor(dut):
    instruction = assemble_rv32im("xor x3, x1, x2")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x0000000A
    dut.operand_b.value = 0x0000000C

    await Timer(1, unit="ns")

    observed_result = int(dut.result.value)
    expected_result = 0x00000006
    assert observed_result == expected_result, (
        f"expected XOR result 0x{expected_result:08X}, "
        f"observed 0x{observed_result:08X}"
    )

    observed_branch_taken = int(dut.branch_taken.value)
    assert observed_branch_taken == 0, (
        f"expected branch_taken 0x0, observed 0x{observed_branch_taken:X}"
    )
