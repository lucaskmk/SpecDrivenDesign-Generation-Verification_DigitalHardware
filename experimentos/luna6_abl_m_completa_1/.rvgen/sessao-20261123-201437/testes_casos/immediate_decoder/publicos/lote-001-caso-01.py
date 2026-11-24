import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the LUI source used by this test into its RV32IM instruction."""
    mnemonic, operands = source.split(None, 1)
    rd_text, immediate_text = (part.strip() for part in operands.split(","))
    if mnemonic.lower() != "lui":
        raise ValueError(f"Unsupported instruction: {mnemonic}")

    rd = int(rd_text.lower().removeprefix("x"))
    immediate = int(immediate_text, 0)
    if not 0 <= rd < 32 or not 0 <= immediate <= 0xFFFFF:
        raise ValueError("LUI register or immediate is out of range")

    return (immediate << 12) | (rd << 7) | 0x37


@cocotb.test()
async def u_immediate_does_not_sign_extend(dut):
    # The legal LUI source sets instruction bit 31.
    dut.instr.value = assemble_rv32im("lui x1, 0x80000")
    await Timer(1, unit="ns")

    observed = int(dut.imm_u.value)
    assert (observed >> 31) & 1 == 1, (
        f"Expected imm_u[31]=1, observed imm_u=0x{observed:08X}"
    )
    assert observed & 0xFFF == 0, (
        f"Expected imm_u[11:0]=0x000, observed imm_u=0x{observed:08X}"
    )
