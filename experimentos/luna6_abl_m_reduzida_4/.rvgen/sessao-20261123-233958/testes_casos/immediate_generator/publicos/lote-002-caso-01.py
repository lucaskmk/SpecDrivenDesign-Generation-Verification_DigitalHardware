import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source: str) -> int:
    """Assemble the LUI instruction used by this test."""
    parts = source.replace(",", " ").split()
    if len(parts) != 3 or parts[0].lower() != "lui":
        raise ValueError(f"Unsupported instruction: {source}")

    rd_text = parts[1].lower()
    if not rd_text.startswith("x"):
        raise ValueError(f"Expected an integer register: {parts[1]}")

    rd = int(rd_text[1:], 10)
    imm = int(parts[2], 0)
    if not 0 <= rd <= 31 or not 0 <= imm <= 0xFFFFF:
        raise ValueError(f"Operand out of range: {source}")

    return (imm << 12) | (rd << 7) | 0x37


@cocotb.test()
async def test_lui_u_immediate_payload_bit(dut):
    dut.instr.value = assemble_rv32im("lui x1, 1")
    await Timer(1, unit="ns")

    observed = int(dut.imm_u.value)
    expected = 0x00001000
    assert observed == expected, (
        f"imm_u: expected 0x{expected:08X}, observed 0x{observed:08X}"
    )
