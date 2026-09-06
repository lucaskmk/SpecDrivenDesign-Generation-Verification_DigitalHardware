# bench_signs_rv32i.asm -- signed/unsigned edge values, RV32I ONLY.
#
# REQ: FR-RV-19 (baseline program proven RV32I-pure by assembling it with
#      allow_m=False), FR-RV-22 (-2^31, 2^31-1 and modular overflow),
#      FR-RV-24 (cycle metrics).
#
# Faithful translation of bench_signs.c. The four multiplications go through
# the shift-and-add routine; everything else is a single RV32I instruction.
#
# Register convention of this file:
#   x18  result area base pointer (RESULT_BASE = 0x00FC8100)
#   x19  INT32_MAX = 2147483647
#   x20  INT32_MIN = -2147483648
#   x5   scratch holding the value about to be stored
#   x10, x11, x28, x29  mul32 argument, operand and scratch
#   x1   link register

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
    mv   x10, x20
    li   x11, -1
    call mul32
    sw   x10, 12(x18)

    # slot 4 -- INT32_MAX * 2 overflows to -2
    mv   x10, x19
    li   x11, 2
    call mul32
    sw   x10, 16(x18)

    # slot 5 -- INT32_MIN * INT32_MIN, low word of 2^62 is zero
    mv   x10, x20
    mv   x11, x20
    call mul32
    sw   x10, 20(x18)

    # slot 6 -- INT32_MAX * INT32_MAX, low word of (2^31-1) squared is one
    mv   x10, x19
    mv   x11, x19
    call mul32
    sw   x10, 24(x18)

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
    li   x10, -1
    li   x11, -1
    call mul32
    sw   x10, 44(x18)

    j    halt

# ---------------------------------------------------------------------------
# mul32: x10 = low 32 bits of (x10 * x11), shift-and-add.
# Leaf routine. Clobbers x10, x11, x28, x29.
# ---------------------------------------------------------------------------
mul32:
    li   x28, 0                 # product = 0
mul32_loop:
    beqz x11, mul32_done        # while (b != 0)
    andi x29, x11, 1
    beqz x29, mul32_shift
    add  x28, x28, x10          # product += a
mul32_shift:
    slli x10, x10, 1
    srli x11, x11, 1            # logical shift, so the loop always ends
    j    mul32_loop
mul32_done:
    mv   x10, x28
    ret

halt:
    j    halt                   # mandatory stop convention (ADR-003)
