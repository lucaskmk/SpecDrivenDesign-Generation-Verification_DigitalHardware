import cocotb
from cocotb.triggers import Timer


MASK32 = 0xFFFFFFFF
MASK64 = (1 << 64) - 1


def to_signed32(value):
    """Interpret a 32-bit value as two's-complement signed."""
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def reference(operand_a, operand_b, op):
    """Arbitrary-precision reference: interpret per op, multiply, reduce mod 2^64, slice."""
    if op == 0x0:
        a_val = to_signed32(operand_a)
        b_val = to_signed32(operand_b)
    elif op == 0x1:
        a_val = to_signed32(operand_a)
        b_val = to_signed32(operand_b)
    elif op == 0x2:
        a_val = to_signed32(operand_a)
        b_val = operand_b & MASK32
    else:
        a_val = operand_a & MASK32
        b_val = operand_b & MASK32
    product64 = (a_val * b_val) & MASK64
    if op == 0x0:
        return product64 & MASK32
    return (product64 >> 32) & MASK32


@cocotb.test()
async def test_multiplier_op_selection_all_ones(dut):
    """Hold the all-ones operand pair fixed; sweep op over MUL, MULH, MULHSU."""
    operand_a = 0xFFFFFFFF
    operand_b = 0xFFFFFFFF

    # Initialize all inputs with known 0/1 values.
    dut.operand_a.value = operand_a
    dut.operand_b.value = operand_b
    dut.op.value = 0x3
    await Timer(1, unit="ns")

    # Witness from the smoke test: MULHU on the all-ones pair.
    observed_mulhu = int(dut.result.value)
    expected_mulhu = reference(operand_a, operand_b, 0x3)
    assert observed_mulhu == expected_mulhu, (
        f"MULHU all-ones (op=0x3): expected result 0x{expected_mulhu:08X}, "
        f"observed 0x{observed_mulhu:08X}"
    )

    names = {0x0: "MUL", 0x1: "MULH", 0x2: "MULHSU"}
    results = {0x3: observed_mulhu}

    for op in (0x0, 0x1, 0x2):
        # Only op changes; operands are left untouched.
        dut.op.value = op
        await Timer(1, unit="ns")

        expected = reference(operand_a, operand_b, op)
        observed = int(dut.result.value)
        assert observed == expected, (
            f"{names[op]} (op=0x{op:X}) 0xFFFFFFFF x 0xFFFFFFFF: "
            f"expected result 0x{expected:08X}, observed 0x{observed:08X}"
        )
        results[op] = observed

    # The four results must be pairwise distinct: op alone selects the result.
    ops = sorted(results)
    for i in range(len(ops)):
        for j in range(i + 1, len(ops)):
            ra = results[ops[i]]
            rb = results[ops[j]]
            assert ra != rb, (
                f"op=0x{ops[i]:X} and op=0x{ops[j]:X} on the all-ones pair must differ: "
                f"expected distinct results, observed both 0x{ra:08X}"
            )
