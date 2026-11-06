import re

import cocotb
from cocotb.triggers import Timer


def assemble_rv32i(source):
    """Assemble the SB source used by this test into one RV32I instruction."""
    match = re.fullmatch(r"\s*sb\s+x(\d+)\s*,\s*(-?\d+)\(x(\d+)\)\s*", source)
    if match is None:
        raise ValueError(f"unsupported RV32I source: {source!r}")

    rs2 = int(match.group(1))
    immediate = int(match.group(2))
    rs1 = int(match.group(3))

    if not 0 <= rs1 < 32 or not 0 <= rs2 < 32:
        raise ValueError("register number is outside the RV32I register range")
    if not -2048 <= immediate <= 2047:
        raise ValueError("SB immediate is outside the signed 12-bit range")

    imm12 = immediate & 0xFFF
    return (
        ((imm12 >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | ((imm12 & 0x1F) << 7)
        | 0x23
    )


@cocotb.test()
async def test_store_data_passthrough(dut):
    dut.instr.value = assemble_rv32i("sb x7, 12(x5)")
    dut.effective_address.value = 0x1234567B
    dut.store_data_in.value = 0xA1B2C3D4
    dut.data_read_data.value = 0xD3A5C67E

    await Timer(1, unit="ns")

    observed_write = int(dut.data_write.value)
    assert observed_write == 1, (
        f"expected data_write 1, observed {observed_write}"
    )

    observed_data = int(dut.data_write_data.value)
    assert observed_data == 0xA1B2C3D4, (
        f"expected data_write_data 0xA1B2C3D4, "
        f"observed 0x{observed_data:08X}"
    )
