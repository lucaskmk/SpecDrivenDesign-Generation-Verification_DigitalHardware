import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1

OP_MULH = 0x1
OP_MULHSU = 0x2
OP_MULHU = 0x3


def to_signed32(value):
    """Interpret a 32-bit value as two's complement."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def reference_high(op, a, b):
    """Independent arbitrary-precision reference: high word of P mod 2^64."""
    if op == OP_MULH:
        a_val, b_val = to_signed32(a), to_signed32(b)
    elif op == OP_MULHSU:
        a_val, b_val = to_signed32(a), b & MASK32
    elif op == OP_MULHU:
        a_val, b_val = a & MASK32, b & MASK32
    else:
        raise ValueError("unsupported op for high-word reference")
    product64 = (a_val * b_val) & MASK64
    return (product64 >> 32) & MASK32


async def run_op(dut, a, b, op):
    """Drive one input triple, wait for settling, and return the result."""
    dut.operand_a.value = a
    dut.operand_b.value = b
    dut.op.value = op
    await Timer(1, unit="ns")
    return int(dut.result.value)


@cocotb.test()
async def test_multiplier_operand_b_signedness_isolated(dut):
    """Flip only operand_b[31] with a small positive operand_a and compare
    MULH (signed b) against MULHSU/MULHU (unsigned b)."""
    # Known initial state for all inputs.
    dut.operand_a.value = 0x00000000
    dut.operand_b.value = 0x00000000
    dut.op.value = 0x0
    await Timer(1, unit="ns")

    operand_a = 0x00000007  # small positive, bit 31 clear
    b_clear = 0x7FFFFFFD    # bit 31 clear
    b_set = 0xFFFFFFFD      # same low bits, bit 31 set

    assert (b_clear ^ b_set) == 0x80000000, "stimulus must differ only in bit 31"

    names = {OP_MULH: "MULH", OP_MULHSU: "MULHSU", OP_MULHU: "MULHU"}
    observed = {}

    for b_val in (b_clear, b_set):
        for op in (OP_MULH, OP_MULHSU, OP_MULHU):
            expected = reference_high(op, operand_a, b_val)
            got = await run_op(dut, operand_a, b_val, op)
            observed[(b_val, op)] = got
            assert got == expected, (
                f"{names[op]} 0x{operand_a:08X} x 0x{b_val:08X}: "
                f"expected result 0x{expected:08X}, observed 0x{got:08X}"
            )

    # Relation 1: with operand_b[31] = 0, all three high words agree.
    h = observed[(b_clear, OP_MULH)]
    hsu = observed[(b_clear, OP_MULHSU)]
    hu = observed[(b_clear, OP_MULHU)]
    assert h == hsu == hu, (
        f"operand_b[31]=0: expected MULH, MULHSU, MULHU equal, observed "
        f"0x{h:08X}, 0x{hsu:08X}, 0x{hu:08X}"
    )

    # Relation 2: with operand_b[31] = 1, MULHSU equals MULHU.
    h = observed[(b_set, OP_MULH)]
    hsu = observed[(b_set, OP_MULHSU)]
    hu = observed[(b_set, OP_MULHU)]
    assert hsu == hu, (
        f"operand_b[31]=1: expected MULHSU == MULHU, observed "
        f"0x{hsu:08X} and 0x{hu:08X}"
    )

    # Relation 3: with operand_b[31] = 1, MULH differs from both and is the
    # all-ones negative-product word.
    assert h != hsu and h != hu, (
        f"operand_b[31]=1: expected MULH to differ from MULHSU/MULHU, observed "
        f"MULH 0x{h:08X}, MULHSU 0x{hsu:08X}, MULHU 0x{hu:08X}"
    )
    assert h == 0xFFFFFFFF, (
        f"operand_b[31]=1: expected MULH 0xFFFFFFFF, observed 0x{h:08X}"
    )
    assert hsu == 0x00000006, (
        f"operand_b[31]=1: expected MULHSU 0x00000006, observed 0x{hsu:08X}"
    )
