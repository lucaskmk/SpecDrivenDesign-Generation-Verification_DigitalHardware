# bench_signs_rv32im.asm -- signed/unsigned edge values, RV32IM.
#
# REQ: FR-RV-12 (RV32IM extension), FR-RV-13 (MUL), FR-RV-22 (-2^31, 2^31-1
#      and modular overflow), FR-RV-24 (cycle metrics against the RV32I
#      version).
#
# Same computation and same published results as bench_signs_rv32i.asm: the
# four calls to the shift-and-add routine become four MUL instructions, which
# is where the whole cycle difference of this benchmark comes from.
#
# Register convention of this file:
#   x18  result area base pointer (RESULT_BASE = 0x00FC8100)
#   x19  INT32_MAX = 2147483647
#   x20  INT32_MIN = -2147483648
#   x5   scratch holding the value about to be stored
#   x11  second multiplication operand

    li   x18, 0x00FC8100        # RESULT_BASE
    li   x19, 2147483647        # INT32_MAX
    li   x20, -2147483648       # INT32_MIN

    # slot 0 -- INT32_MAX + 1 wraps around to INT32_MIN
    addi x5, x19, 1
    sw   x5, 0(x18)

    # slot 1 -- INT32_MIN + (-1) wraps around to INT32_MAX
    addi x5, x20, -1
    sw   x5, 4(x18)

    # slot 2 -- 0 - INT32_MIN is INT32_MIN again: no positive counterpart
    sub  x5, x0, x20
    sw   x5, 8(x18)

    # slot 3 -- INT32_MIN * -1, same modular result
    li   x11, -1
    mul  x5, x20, x11
    sw   x5, 12(x18)

    # slot 4 -- INT32_MAX * 2 overflows to -2
    li   x11, 2
    mul  x5, x19, x11
    sw   x5, 16(x18)

    # slot 5 -- INT32_MIN * INT32_MIN, low word of 2^62 is zero
    mul  x5, x20, x20
    sw   x5, 20(x18)

    # slot 6 -- INT32_MAX * INT32_MAX, low word of (2^31-1) squared is one
    mul  x5, x19, x19
    sw   x5, 24(x18)

    # slot 7 -- signed comparison: INT32_MIN is the smallest
    slt  x5, x20, x19
    sw   x5, 28(x18)

    # slot 8 -- unsigned comparison: 0x80000000 is above 0x7FFFFFFF
    sltu x5, x20, x19
    sw   x5, 32(x18)

    # slot 9 -- arithmetic shift keeps the sign bit
    srai x5, x20, 31
    sw   x5, 36(x18)

    # slot 10 -- logical shift brings the sign bit down as a plain one
    srli x5, x20, 31
    sw   x5, 40(x18)

    # slot 11 -- (-1) * (-1)
    li   x11, -1
    mul  x5, x11, x11
    sw   x5, 44(x18)

halt:
    j    halt                   # mandatory stop convention (ADR-003)
