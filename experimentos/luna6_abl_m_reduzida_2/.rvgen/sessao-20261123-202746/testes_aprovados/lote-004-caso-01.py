import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the BEQ instructions and labels used by this test."""
    instructions = []
    labels = {}
    pc = 0

    for raw_line in source.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue

        if ":" in line:
            label, line = line.split(":", 1)
            labels[label.strip()] = pc
            line = line.strip()
            if not line:
                continue

        instructions.append((pc, line))
        pc += 4

    words = []
    for instruction_pc, line in instructions:
        mnemonic, operands = line.split(None, 1)
        if mnemonic.lower() != "beq":
            raise ValueError(f"Unsupported instruction: {mnemonic}")

        rs1_text, rs2_text, target_text = (
            operand.strip() for operand in operands.split(",")
        )
        rs1 = int(rs1_text.lower().removeprefix("x"))
        rs2 = int(rs2_text.lower().removeprefix("x"))
        target = labels[target_text]
        offset = target - instruction_pc

        if offset % 2 != 0 or not -(1 << 12) <= offset < (1 << 12):
            raise ValueError(f"Invalid BEQ target offset: {offset}")

        immediate = offset & 0x1FFF
        word = (
            (((immediate >> 12) & 0x1) << 31)
            | (((immediate >> 5) & 0x3F) << 25)
            | (rs2 << 20)
            | (rs1 << 15)
            | (((immediate >> 1) & 0xF) << 8)
            | (((immediate >> 11) & 0x1) << 7)
            | 0x63
        )
        words.append(word)

    return words


@cocotb.test()
async def test_valid_beq_asserts_branch_enable(dut):
    program = assemble_rv32im(
        """
        beq x1, x2, target
        target: beq x0, x0, target
        """
    )
    instruction = program[0]

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    await Timer(1, unit="ns")

    assert int(dut.branch_enable.value) == 1, (
        f"Expected branch_enable=1, observed {int(dut.branch_enable.value)}"
    )
