import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the branch and ADDI instructions used by this test."""
    lines = [line.strip() for line in source.splitlines() if line.strip()]
    labels = {}
    instructions = []
    pc = 0

    for line in lines:
        if line.endswith(":"):
            labels[line[:-1]] = pc
            continue
        instructions.append((pc, line))
        pc += 4

    words = []
    for pc, line in instructions:
        mnemonic, operands = line.split(None, 1)
        operands = [operand.strip() for operand in operands.split(",")]

        if mnemonic == "beq":
            rs1 = int(operands[0][1:])
            rs2 = int(operands[1][1:])
            displacement = labels[operands[2]] - pc
            immediate = displacement & 0x1FFF
            word = (
                (((immediate >> 12) & 0x1) << 31)
                | (((immediate >> 5) & 0x3F) << 25)
                | (rs2 << 20)
                | (rs1 << 15)
                | (((immediate >> 1) & 0xF) << 8)
                | (((immediate >> 11) & 0x1) << 7)
                | 0x63
            )
        elif mnemonic == "addi":
            rd = int(operands[0][1:])
            rs1 = int(operands[1][1:])
            immediate = int(operands[2], 0) & 0xFFF
            word = (immediate << 20) | (rs1 << 15) | (rd << 7) | 0x13
        else:
            raise ValueError(f"Unsupported instruction in test source: {mnemonic}")

        words.append(word)

    return words


@cocotb.test()
async def test_branch_immediate_implicit_low_bit(dut):
    program = assemble_rv32i(
        """
        beq x1, x2, target
        addi x0, x0, 0
        target:
        """
    )
    dut.instr.value = program[0]
    await Timer(1, unit="ns")

    observed = int(dut.imm_b.value)
    assert (observed & 0x1) == 0x0, (
        f"expected imm_b[0]=0x0, observed imm_b[0]=0x{observed & 0x1:X}"
    )
