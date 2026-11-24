import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal OP-IMM instruction used by this standalone test."""
    parts = source.replace(",", "").split()
    if len(parts) != 4 or parts[0] != "xori":
        raise ValueError(f"unsupported assembly source: {source}")

    def register_number(name):
        if not name.startswith("x"):
            raise ValueError(f"invalid register: {name}")
        number = int(name[1:])
        if not 0 <= number <= 31:
            raise ValueError(f"register out of range: {name}")
        return number

    rd = register_number(parts[1])
    rs1 = register_number(parts[2])
    immediate = int(parts[3], 0)
    if not -2048 <= immediate <= 2047:
        raise ValueError("OP-IMM immediate is out of range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (0x4 << 12)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_xori_returns_bitwise_xor(dut):
    instruction = assemble_rv32im("xori x3, x5, 7")

    dut.opcode.value = instruction & 0x7F
    dut.funct3.value = (instruction >> 12) & 0x7
    dut.funct7.value = (instruction >> 25) & 0x7F
    dut.operand_a.value = 0x00000013
    dut.operand_b.value = 0x00000007

    await Timer(1, unit="ns")

    observed = int(dut.result.value)
    assert observed == 0x00000014, (
        f"expected 0x00000014, observed 0x{observed:08X}"
    )
