import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ADDI source used by this test into one RV32IM instruction."""
    fields = source.replace(",", " ").split()
    if len(fields) != 4 or fields[0].lower() != "addi":
        raise ValueError(f"Unsupported assembly source: {source}")

    def parse_register(token):
        token = token.lower()
        if not token.startswith("x"):
            raise ValueError(f"Expected an integer register, got {token}")
        register = int(token[1:])
        if not 0 <= register < 32:
            raise ValueError(f"Register out of range: {token}")
        return register

    rd = parse_register(fields[1])
    rs1 = parse_register(fields[2])
    immediate = int(fields[3], 0)
    if not -2048 <= immediate <= 2047:
        raise ValueError(f"ADDI immediate out of range: {immediate}")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_i_type_zero_sign_extension(dut):
    instruction = assemble_rv32im("addi x5, x6, 0x5A3")
    dut.instr.value = instruction

    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    expected = 0x000005A3
    assert observed == expected, (
        f"expected imm_i 0x{expected:08X} with zero upper extension bits, "
        f"observed 0x{observed:08X}"
    )
