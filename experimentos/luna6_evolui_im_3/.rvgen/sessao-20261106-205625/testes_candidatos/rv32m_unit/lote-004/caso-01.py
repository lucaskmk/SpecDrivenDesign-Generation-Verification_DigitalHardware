import cocotb
from cocotb.triggers import Timer


def encode_rv32m(mnemonic, rd, rs1, rs2):
    """Encode one RV32M R-type instruction."""
    funct3_by_mnemonic = {
        "mul": 0x0,
        "mulh": 0x1,
        "mulhsu": 0x2,
        "mulhu": 0x3,
        "div": 0x4,
        "divu": 0x5,
        "rem": 0x6,
        "remu": 0x7,
    }
    funct3 = funct3_by_mnemonic[mnemonic.lower()]
    return (
        (0x01 << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (rd << 7)
        | 0x33
    )


@cocotb.test()
async def mul_returns_low_32_bits_for_wide_product(dut):
    dut.instr.value = encode_rv32m("mul", rd=3, rs1=1, rs2=2)
    dut.operand_a.value = 0x12345678 & 0xFFFFFFFF
    dut.operand_b.value = 0x23456789 & 0xFFFFFFFF

    await Timer(1, unit="ns")

    full_product = 0x12345678 * 0x23456789
    expected = full_product & 0xFFFFFFFF
    assert full_product >> 32 != 0, "Test product must have nonzero upper 32 bits"
    assert expected != 0, "Test product must have a nonzero low 32-bit result"
    assert int(dut.valid.value) == 1, (
        f"Expected valid = 1, observed {int(dut.valid.value)}"
    )
    observed = int(dut.result.value)
    assert observed == expected, (
        f"Expected result 0x{expected:08X}, observed 0x{observed:08X}"
    )
