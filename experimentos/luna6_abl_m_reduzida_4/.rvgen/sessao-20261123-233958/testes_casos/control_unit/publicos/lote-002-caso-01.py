import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the LUI source used by this test into one RV32IM instruction."""
    match = re.fullmatch(
        r"\s*lui\s+x([0-9]+)\s*,\s*(0x[0-9a-fA-F]+|[0-9]+)\s*",
        source,
        re.IGNORECASE,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM source: {source!r}")

    rd = int(match.group(1), 10)
    upper_imm = int(match.group(2), 0)
    if not 0 <= rd < 32:
        raise ValueError(f"Register index out of range: x{rd}")
    if not 0 <= upper_imm < (1 << 20):
        raise ValueError(f"LUI immediate out of range: {upper_imm:#x}")

    # Encode the legal LUI source: imm[31:12] | rd | opcode.
    return [(upper_imm << 12) | (rd << 7) | 0x37]


@cocotb.test()
async def lui_selects_u_type_immediate(dut):
    dut.instr.value = assemble_rv32im("lui x7, 0xABCDE")[0]
    await Timer(1, unit="ns")

    observed = int(dut.imm_sel.value)
    assert observed == 0x4, (
        f"Expected imm_sel=0x4, observed 0x{observed:X}"
    )
