import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the single legal LUI instruction used by this test."""
    mnemonic, operands = source.split(None, 1)
    rd_text, immediate_text = (part.strip() for part in operands.split(",", 1))

    if mnemonic.lower() != "lui" or not rd_text.lower().startswith("x"):
        raise ValueError(f"Unsupported RV32IM instruction: {source}")

    rd = int(rd_text[1:], 0)
    immediate = int(immediate_text, 0)
    if not 0 <= rd <= 31 or not 0 <= immediate <= 0xFFFFF:
        raise ValueError(f"Invalid LUI operands: {source}")

    return ((immediate & 0xFFFFF) << 12) | (rd << 7) | 0x37


@cocotb.test()
async def test_u_immediate_top_bit_does_not_sign_extend(dut):
    # LUI sets instr[31] while all other U-immediate source bits are zero.
    dut.instr.value = assemble_rv32im("lui x1, 0x80000")
    await Timer(1, unit="ns")

    imm_u = int(dut.imm_u.value)
    assert (imm_u >> 31) & 1 == 1, (
        f"imm_u[31] expected 1, observed 0x{imm_u:08X}"
    )
    assert imm_u & 0xFFF == 0, (
        f"imm_u[11:0] expected 0x000, observed 0x{imm_u & 0xFFF:03X}"
    )
