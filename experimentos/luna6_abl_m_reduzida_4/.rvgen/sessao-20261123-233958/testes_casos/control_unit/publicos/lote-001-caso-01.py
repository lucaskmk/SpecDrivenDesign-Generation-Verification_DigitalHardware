import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32im(source):
    """Assemble the legal LUI source used by this standalone test."""
    match = re.fullmatch(
        r"\s*lui\s+x([0-9]+)\s*,\s*(0x[0-9a-fA-F]+|[0-9]+)\s*",
        source,
    )
    if match is None:
        raise ValueError(f"Unsupported RV32IM assembly source: {source!r}")

    rd = int(match.group(1), 10)
    immediate = int(match.group(2), 0)
    if not 0 <= rd < 32:
        raise ValueError("LUI destination register must be between x0 and x31")
    if not 0 <= immediate < (1 << 20):
        raise ValueError("LUI immediate must fit in 20 bits")

    return (immediate << 12) | (rd << 7) | 0x37


@cocotb.test()
async def lui_selects_pass_b(dut):
    dut.instr.value = assemble_rv32im("lui x19, 0xABCDE")
    await Timer(1, unit="ns")

    observed = int(dut.alu_op.value)
    assert observed == 0x0A, (
        f"Expected alu_op=0x0A (PASS_B), observed 0x{observed:02X}"
    )
