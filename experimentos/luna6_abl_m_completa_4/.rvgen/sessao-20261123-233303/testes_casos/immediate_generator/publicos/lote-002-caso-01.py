import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the ADDI source used by this test."""
    fields = source.replace(",", " ").split()
    if len(fields) != 4 or fields[0].lower() != "addi":
        raise ValueError(f"Unsupported RV32IM source: {source}")

    rd = int(fields[1].lower().removeprefix("x"))
    rs1 = int(fields[2].lower().removeprefix("x"))
    immediate = int(fields[3], 0)

    if not (0 <= rd < 32 and 0 <= rs1 < 32):
        raise ValueError("Register index is outside the RV32 register range")
    if not (-2048 <= immediate <= 2047):
        raise ValueError("ADDI immediate is outside the signed 12-bit range")

    return (
        ((immediate & 0xFFF) << 20)
        | (rs1 << 15)
        | (rd << 7)
        | 0x13
    )


@cocotb.test()
async def test_negative_addi_immediate_sign_extension(dut):
    source = "addi x5, x6, -17"
    instruction = assemble_rv32im(source)
    expected_imm_i = (-17) & 0xFFFFFFFF

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_i.value)
    assert observed == expected_imm_i, (
        f"expected imm_i 0x{expected_imm_i:08X}, "
        f"observed 0x{observed:08X}"
    )
