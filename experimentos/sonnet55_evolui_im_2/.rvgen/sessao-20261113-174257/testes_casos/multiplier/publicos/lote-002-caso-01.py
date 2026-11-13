import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1

OP_MULH = 0x1
OP_MULHSU = 0x2
OP_MULHU = 0x3

OP_NAMES = {
    OP_MULH: "MULH",
    OP_MULHSU: "MULHSU",
    OP_MULHU: "MULHU",
}


def to_signed32(value):
    """Interpret a 32-bit integer as two's complement."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def reference_high(operand_a, operand_b, op):
    """Independent arbitrary-precision reference for the high word."""
    if op == OP_MULH:
        a_val = to_signed32(operand_a)
        b_val = to_signed32(operand_b)
    elif op == OP_MULHSU:
        a_val = to_signed32(operand_a)
        b_val = operand_b & MASK32
    elif op == OP_MULHU:
        a_val = operand_a & MASK32
        b_val = operand_b & MASK32
    else:
        raise ValueError("unsupported op for high-word reference")
    product64 = (a_val * b_val) & MASK64
    return (product64 >> 32) & MASK32


async def drive_and_read(dut, operand_a, operand_b, op):
    """Drive the three inputs, let the logic settle, and return result."""
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.op.value = op
    await Timer(1, unit="ns")
    return int(dut.result.value)


@cocotb.test()
async def test_operand_a_sign_bit_isolated(dut):
    """Flipping only operand_a[31] changes MULH/MULHSU (signed) but not as
    an unsigned value for MULHU, with operand_b fixed small positive."""
    # Initialize to a known state with only 0/1 values.
    dut.operand_a.value = 0x00000000
    dut.operand_b.value = 0x00000000
    dut.op.value = 0x0
    await Timer(1, unit="ns")

    operand_b = 0x00000007
    low_bits = 0x7FFFFFFD
    operand_a_pos = low_bits              # bit 31 = 0
    operand_a_neg = low_bits | 0x80000000  # bit 31 = 1, same low bits

    assert (operand_a_pos ^ operand_a_neg) == 0x80000000, (
        "stimulus error: operand_a values must differ only in bit 31"
    )
    assert (operand_b & 0x80000000) == 0, (
        "stimulus error: operand_b bit 31 must be clear"
    )

    observed = {}
    for label, operand_a in (("a31=0", operand_a_pos), ("a31=1", operand_a_neg)):
        for op in (OP_MULH, OP_MULHSU, OP_MULHU):
            expected = reference_high(operand_a, operand_b, op)
            got = await drive_and_read(dut, operand_a, operand_b, op)
            observed[(label, op)] = got
            assert got == expected, (
                f"{OP_NAMES[op]} operand_a=0x{operand_a:08X} "
                f"operand_b=0x{operand_b:08X} ({label}): "
                f"expected result 0x{expected:08X}, observed 0x{got:08X}"
            )

    # Relations stated by the plan, using the reference values.
    # With operand_a[31]=0 all three high words agree.
    pos_vals = [observed[("a31=0", op)] for op in (OP_MULH, OP_MULHSU, OP_MULHU)]
    assert pos_vals[0] == pos_vals[1] == pos_vals[2], (
        f"with operand_a[31]=0 expected all high words equal, observed "
        f"MULH=0x{pos_vals[0]:08X} MULHSU=0x{pos_vals[1]:08X} "
        f"MULHU=0x{pos_vals[2]:08X}"
    )

    # With operand_a[31]=1 MULH and MULHSU are all ones, MULHU differs.
    mulh_neg = observed[("a31=1", OP_MULH)]
    mulhsu_neg = observed[("a31=1", OP_MULHSU)]
    mulhu_neg = observed[("a31=1", OP_MULHU)]
    assert mulh_neg == 0xFFFFFFFF, (
        f"MULH with operand_a[31]=1: expected result 0xFFFFFFFF, "
        f"observed 0x{mulh_neg:08X}"
    )
    assert mulhsu_neg == 0xFFFFFFFF, (
        f"MULHSU with operand_a[31]=1: expected result 0xFFFFFFFF, "
        f"observed 0x{mulhsu_neg:08X}"
    )
    assert mulhu_neg != mulh_neg and mulhu_neg != mulhsu_neg, (
        f"MULHU with operand_a[31]=1 must differ from signed results: "
        f"MULH=0x{mulh_neg:08X} MULHSU=0x{mulhsu_neg:08X} "
        f"MULHU=0x{mulhu_neg:08X}"
    )
    assert mulhu_neg < 0x10, (
        f"MULHU with operand_a[31]=1 expected small positive high word, "
        f"observed 0x{mulhu_neg:08X}"
    )
