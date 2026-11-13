import cocotb
from cocotb.triggers import Timer

OP_MUL = 0x0
OP_MULH = 0x1
OP_MULHSU = 0x2
OP_MULHU = 0x3


def _to_signed32(val: int) -> int:
    val &= 0xFFFFFFFF
    return val - 0x100000000 if (val & 0x80000000) else val


def _expected_mul_result(op: int, a: int, b: int) -> int:
    u_a = a & 0xFFFFFFFF
    u_b = b & 0xFFFFFFFF
    s_a = _to_signed32(u_a)
    s_b = _to_signed32(u_b)

    if op == OP_MUL:
        return (u_a * u_b) & 0xFFFFFFFF
    if op == OP_MULH:
        return ((s_a * s_b) >> 32) & 0xFFFFFFFF
    if op == OP_MULHSU:
        return ((s_a * u_b) >> 32) & 0xFFFFFFFF
    if op == OP_MULHU:
        return ((u_a * u_b) >> 32) & 0xFFFFFFFF
    raise ValueError(f"Unsupported multiplication selector 0x{op:X}")


async def _drive_and_read(dut, op: int, a: int, b: int) -> int:
    dut.muldiv_op.value = op & 0x7
    dut.operand_a.value = a & 0xFFFFFFFF
    dut.operand_b.value = b & 0xFFFFFFFF
    await Timer(1, unit="ns")
    return int(dut.result.value)


@cocotb.test()
async def test_muldiv_unit_mul_signedness_and_operand_order(dut):
    # Initialize all public inputs deterministically before observations
    await _drive_and_read(dut, OP_MUL, 0x00000001, 0x00000001)

    mul_ops = (
        (OP_MUL, "MUL"),
        (OP_MULH, "MULH"),
        (OP_MULHSU, "MULHSU"),
        (OP_MULHU, "MULHU"),
    )

    # Non-trivial 32-bit magnitudes spanning into bits [63:32] across all four sign quadrants:
    # (MSB=0, MSB=0), (MSB=1, MSB=0), (MSB=0, MSB=1), and (MSB=1, MSB=1)
    pos_x = 0x5379BDF1
    pos_y = 0x369CF258
    neg_x = 0xAC86420F
    neg_y = 0xC9630DA8

    quadrant_pairs = (
        (pos_x, pos_y),
        (neg_x, pos_y),
        (pos_x, neg_y),
        (neg_x, neg_y),
    )

    for op_code, op_name in mul_ops:
        for op_a, op_b in quadrant_pairs:
            obs_ab = await _drive_and_read(dut, op_code, op_a, op_b)
            exp_ab = _expected_mul_result(op_code, op_a, op_b)
            assert obs_ab == exp_ab, (
                f"{op_name} (muldiv_op=0x{op_code:X}) quadrant mismatch for "
                f"operand_a=0x{op_a:08X}, operand_b=0x{op_b:08X}: "
                f"expected 0x{exp_ab:08X}, observed 0x{obs_ab:08X}"
            )

            obs_ba = await _drive_and_read(dut, op_code, op_b, op_a)
            exp_ba = _expected_mul_result(op_code, op_b, op_a)
            assert obs_ba == exp_ba, (
                f"{op_name} (muldiv_op=0x{op_code:X}) swapped quadrant mismatch for "
                f"operand_a=0x{op_b:08X}, operand_b=0x{op_a:08X}: "
                f"expected 0x{exp_ba:08X}, observed 0x{obs_ba:08X}"
            )

            a_neg = bool(op_a & 0x80000000)
            b_neg = bool(op_b & 0x80000000)
            if op_code == OP_MULHSU and (a_neg != b_neg):
                assert obs_ab != obs_ba, (
                    f"MULHSU (muldiv_op=0x{op_code:X}) must change upper word when swapping "
                    f"opposite-sign operands 0x{op_a:08X} and 0x{op_b:08X}, "
                    f"but both produced 0x{obs_ab:08X}"
                )
            elif op_code in (OP_MUL, OP_MULH, OP_MULHU):
                assert obs_ab == obs_ba, (
                    f"{op_name} (muldiv_op=0x{op_code:X}) must be commutative when swapping "
                    f"0x{op_a:08X} and 0x{op_b:08X}: forward=0x{obs_ab:08X}, swapped=0x{obs_ba:08X}"
                )

    # Explicit opposite-sign swap witness Pairs:
    # (0xFFFFFFF9, 0x00000003) -> MULHSU forward=0xFFFFFFFF, swapped=0x00000002
    # (0x80000000, 0x00000003) -> MULHSU forward=0xFFFFFFFE, swapped=0x00000001
    swap_witness_pairs = (
        (0xFFFFFFF9, 0x00000003, 0xFFFFFFFF, 0x00000002),
        (0x80000000, 0x00000003, 0xFFFFFFFE, 0x00000001),
    )

    for neg_val, pos_val, exp_mulhsu_fwd, exp_mulhsu_rev in swap_witness_pairs:
        obs_mulhsu_fwd = await _drive_and_read(dut, OP_MULHSU, neg_val, pos_val)
        assert obs_mulhsu_fwd == exp_mulhsu_fwd, (
            f"MULHSU signed-operand_a check failed for operand_a=0x{neg_val:08X}, "
            f"operand_b=0x{pos_val:08X}: expected 0x{exp_mulhsu_fwd:08X}, observed 0x{obs_mulhsu_fwd:08X}"
        )

        obs_mulhsu_rev = await _drive_and_read(dut, OP_MULHSU, pos_val, neg_val)
        assert obs_mulhsu_rev == exp_mulhsu_rev, (
            f"MULHSU unsigned-operand_b check failed for operand_a=0x{pos_val:08X}, "
            f"operand_b=0x{neg_val:08X}: expected 0x{exp_mulhsu_rev:08X}, observed 0x{obs_mulhsu_rev:08X}"
        )
        assert obs_mulhsu_fwd != obs_mulhsu_rev, (
            f"MULHSU did not distinguish operand order for 0x{neg_val:08X} and 0x{pos_val:08X}: "
            f"both produced 0x{obs_mulhsu_fwd:08X}"
        )

        for sym_op, sym_name in ((OP_MUL, "MUL"), (OP_MULH, "MULH"), (OP_MULHU, "MULHU")):
            fwd = await _drive_and_read(dut, sym_op, neg_val, pos_val)
            rev = await _drive_and_read(dut, sym_op, pos_val, neg_val)
            exp_sym = _expected_mul_result(sym_op, neg_val, pos_val)
            assert fwd == exp_sym and rev == exp_sym, (
                f"{sym_name} (muldiv_op=0x{sym_op:X}) commutativity/value mismatch for "
                f"0x{neg_val:08X} and 0x{pos_val:08X}: expected 0x{exp_sym:08X}, "
                f"observed forward=0x{fwd:08X}, swapped=0x{rev:08X}"
            )

    # Minimum negative signed boundary pair (0x80000000, 0x80000000) across 0x0..0x3
    min_neg = 0x80000000
    boundary_expectations = (
        (OP_MUL, "MUL", 0x00000000),
        (OP_MULH, "MULH", 0x40000000),
        (OP_MULHSU, "MULHSU", 0xC0000000),
        (OP_MULHU, "MULHU", 0x40000000),
    )

    for op_code, op_name, exp_val in boundary_expectations:
        obs_val = await _drive_and_read(dut, op_code, min_neg, min_neg)
        assert obs_val == exp_val, (
            f"{op_name} (muldiv_op=0x{op_code:X}) minimum negative boundary mismatch for "
            f"operand_a=0x{min_neg:08X}, operand_b=0x{min_neg:08X}: "
            f"expected 0x{exp_val:08X}, observed 0x{obs_val:08X}"
        )
