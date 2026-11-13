import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the JAL instructions used by this standalone test."""
    labels = {}
    instructions = []

    for line in source.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.endswith(":"):
            labels[line[:-1]] = 4 * len(instructions)
        else:
            instructions.append(line)

    words = []
    for index, instruction in enumerate(instructions):
        mnemonic, operands = instruction.split(None, 1)
        rd, target = (part.strip() for part in operands.split(","))
        if mnemonic != "jal" or rd != "x0":
            raise ValueError(f"Unsupported assembly instruction: {instruction}")

        displacement = labels[target] - 4 * index
        if displacement % 2 or not -(1 << 20) <= displacement < (1 << 20):
            raise ValueError(f"JAL displacement out of range: {displacement}")

        imm = displacement & 0x1FFFFF
        word = (
            0x6F
            | (((imm >> 20) & 0x1) << 31)
            | (((imm >> 1) & 0x3FF) << 21)
            | (((imm >> 11) & 0x1) << 20)
            | (((imm >> 12) & 0xFF) << 12)
        )
        words.append(word)

    return words


@cocotb.test()
async def test_backward_jal_sign_extension(dut):
    dut.instr.value = 0x00000000
    await Timer(1, unit="ns")

    program = assemble_rv32im(
        """
    earlier:
        jal x0, earlier
        jal x0, earlier
        """
    )
    dut.instr.value = program[1]
    await Timer(1, unit="ns")

    observed = int(dut.imm_j.value)
    sign_extension_mask = 0xFFE00000
    observed_region = observed & sign_extension_mask
    assert observed_region == sign_extension_mask, (
        f"imm_j sign-extension region: expected 0x{sign_extension_mask:08X}, "
        f"observed 0x{observed_region:08X}"
    )
