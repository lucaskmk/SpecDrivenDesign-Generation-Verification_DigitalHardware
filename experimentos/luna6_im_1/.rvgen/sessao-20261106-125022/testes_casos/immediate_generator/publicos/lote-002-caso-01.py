import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the LUI instruction used by this test."""
    mnemonic, operands = source.strip().split(None, 1)
    rd_text, imm_text = (part.strip() for part in operands.split(","))

    if mnemonic.lower() != "lui" or not rd_text.lower().startswith("x"):
        raise ValueError(f"Unsupported RV32I source: {source}")

    rd = int(rd_text[1:], 10)
    imm20 = int(imm_text, 0)
    if not 0 <= rd < 32 or not 0 <= imm20 < (1 << 20):
        raise ValueError(f"Operand out of range: {source}")

    return (imm20 << 12) | (rd << 7) | 0x37


@cocotb.test()
async def test_u_immediate_packing(dut):
    instruction = assemble_rv32i("lui x5, 0xABCDE")
    expected = 0xABCDE000

    dut.instr.value = instruction
    await Timer(1, unit="ns")

    observed = int(dut.imm_u.value)
    assert (observed >> 12) == 0xABCDE, (
        f"expected imm_u upper bits 0xABCDE, observed 0x{observed >> 12:05X}"
    )
    assert (observed & 0xFFF) == 0x000, (
        f"expected imm_u lower bits 0x000, observed 0x{observed & 0xFFF:03X}"
    )
    assert observed == expected, (
        f"expected imm_u 0x{expected:08X}, observed 0x{observed:08X}"
    )
