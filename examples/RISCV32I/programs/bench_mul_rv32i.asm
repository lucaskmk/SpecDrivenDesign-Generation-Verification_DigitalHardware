# bench_mul_rv32i.asm -- integer multiplication benchmark, RV32I ONLY.
#
# REQ: FR-RV-19 (baseline program proven RV32I-pure by assembling it with
#      allow_m=False), FR-RV-22 (edge operands), FR-RV-24 (cycle metrics).
#
# Faithful translation of bench_mul.c. The multiplication is emulated with
# the shift-and-add loop of mul32() in that file; the low 32 bits it produces
# are exactly what RISC-V MUL defines, so this program and
# bench_mul_rv32im.asm must publish identical words.
#
# Operands are materialised with `li` instead of being read from a table:
# this CPU is a Harvard machine, the instruction ROM is not readable by `lw`
# and the data ROM is only 8 bytes wide (see programs/README.md).
#
# Register convention of this file:
#   x18  result area base pointer (RESULT_BASE = 0x00FC8100)
#   x10  mul32 argument `a`, and the returned product
#   x11  mul32 argument `b`
#   x28  mul32 product accumulator
#   x29  mul32 scratch (current bit of `b`)
#   x1   link register

    li   x18, 0x00FC8100        # RESULT_BASE

    # slot 0 -- 7 * 6, small positive operands
    li   x10, 7
    li   x11, 6
    call mul32
    sw   x10, 0(x18)

    # slot 1 -- 123 * 456, still fits in 32 bits
    li   x10, 123
    li   x11, 456
    call mul32
    sw   x10, 4(x18)

    # slot 2 -- -3 * 5, mixed signs
    li   x10, -3
    li   x11, 5
    call mul32
    sw   x10, 8(x18)

    # slot 3 -- -7 * -8, both operands negative
    li   x10, -7
    li   x11, -8
    call mul32
    sw   x10, 12(x18)

    # slot 4 -- 65535 * 65537, the largest product that still fits: 2^32-1
    li   x10, 65535
    li   x11, 65537
    call mul32
    sw   x10, 16(x18)

    # slot 5 -- INT32_MAX * 2, overflows 32 bits
    li   x10, 2147483647
    li   x11, 2
    call mul32
    sw   x10, 20(x18)

    # slot 6 -- INT32_MIN * 3, overflows 32 bits
    li   x10, -2147483648
    li   x11, 3
    call mul32
    sw   x10, 24(x18)

    # slot 7 -- 0 * 0x12345678, zero operand
    li   x10, 0
    li   x11, 305419896
    call mul32
    sw   x10, 28(x18)

    j    halt

# ---------------------------------------------------------------------------
# mul32: x10 = low 32 bits of (x10 * x11), shift-and-add.
# Leaf routine. Clobbers x10, x11, x28, x29. At most 32 iterations because
# `b` is shifted right logically and therefore always reaches zero.
# ---------------------------------------------------------------------------
mul32:
    li   x28, 0                 # product = 0
mul32_loop:
    beqz x11, mul32_done        # while (b != 0)
    andi x29, x11, 1            # current bit of b
    beqz x29, mul32_shift
    add  x28, x28, x10          # product += a (modular 2^32)
mul32_shift:
    slli x10, x10, 1            # a <<= 1
    srli x11, x11, 1            # b >>= 1, logical
    j    mul32_loop
mul32_done:
    mv   x10, x28               # return the product in x10
    ret

halt:
    j    halt                   # mandatory stop convention (ADR-003)
