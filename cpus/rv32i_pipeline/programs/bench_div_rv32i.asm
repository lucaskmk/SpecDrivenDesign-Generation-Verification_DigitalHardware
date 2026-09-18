# bench_div_rv32i.asm -- division and remainder benchmark, RV32I ONLY.
#
# REQ: FR-RV-19 (baseline program proven RV32I-pure by assembling it with
#      allow_m=False), FR-RV-14 (RISC-V special cases reproduced by the
#      emulation), FR-RV-22 (edge operands), FR-RV-24 (cycle metrics).
#
# Faithful translation of bench_div.c: divrem32() becomes the `divrem`
# routine below, with udivmod32() inlined so the routine stays a leaf and no
# link register has to be saved.
#
# Slot layout: slot 2*i = quotient of case i, slot 2*i+1 = remainder.
#
# Register convention of this file:
#   x18       result area base pointer (RESULT_BASE = 0x00FC8100)
#   x10       dividend in, quotient out
#   x11       divisor in, remainder out
#   x5, x6    divrem scratch (constants, shifted-out bits)
#   x19, x20  sign masks of dividend and divisor
#   x21       sign mask of the quotient
#   x28       partial quotient
#   x29       partial remainder
#   x30       loop counter
#   x1        link register

    li   x18, 0x00FC8100        # RESULT_BASE

    # case 0 -- 100 / 7, both positive
    li   x10, 100
    li   x11, 7
    call divrem
    sw   x10, 0(x18)
    sw   x11, 4(x18)

    # case 1 -- -100 / 7, negative dividend
    li   x10, -100
    li   x11, 7
    call divrem
    sw   x10, 8(x18)
    sw   x11, 12(x18)

    # case 2 -- 100 / -7, negative divisor
    li   x10, 100
    li   x11, -7
    call divrem
    sw   x10, 16(x18)
    sw   x11, 20(x18)

    # case 3 -- -100 / -7, both negative
    li   x10, -100
    li   x11, -7
    call divrem
    sw   x10, 24(x18)
    sw   x11, 28(x18)

    # case 4 -- 7 / 0, divide by zero: q = -1, r = dividend (FR-RV-14)
    li   x10, 7
    li   x11, 0
    call divrem
    sw   x10, 32(x18)
    sw   x11, 36(x18)

    # case 5 -- INT32_MIN / -1, signed overflow: q = INT32_MIN, r = 0
    li   x10, -2147483648
    li   x11, -1
    call divrem
    sw   x10, 40(x18)
    sw   x11, 44(x18)

    # case 6 -- INT32_MAX / 2
    li   x10, 2147483647
    li   x11, 2
    call divrem
    sw   x10, 48(x18)
    sw   x11, 52(x18)

    # case 7 -- INT32_MIN / 3, magnitude needs the full 32-bit unsigned range
    li   x10, -2147483648
    li   x11, 3
    call divrem
    sw   x10, 56(x18)
    sw   x11, 60(x18)

    j    halt

# ---------------------------------------------------------------------------
# divrem: x10 = x10 / x11 (truncated towards zero), x11 = x10 % x11.
# Leaf routine. Clobbers x5, x6, x10, x11, x19, x20, x21, x28, x29, x30.
# ---------------------------------------------------------------------------
divrem:
    bnez x11, divrem_check_overflow

    # divisor == 0: quotient = -1, remainder = dividend (no trap in RISC-V)
    mv   x11, x10
    li   x10, -1
    ret

divrem_check_overflow:
    li   x5, -2147483648
    bne  x10, x5, divrem_general
    li   x6, -1
    bne  x11, x6, divrem_general

    # INT32_MIN / -1: quotient = INT32_MIN, remainder = 0 (no trap)
    li   x10, -2147483648
    li   x11, 0
    ret

divrem_general:
    srai x19, x10, 31           # 0xFFFFFFFF when the dividend is negative
    srai x20, x11, 31           # 0xFFFFFFFF when the divisor is negative
    xor  x10, x10, x19
    sub  x10, x10, x19          # |dividend| as an unsigned word
    xor  x11, x11, x20
    sub  x11, x11, x20          # |divisor|  as an unsigned word

    li   x28, 0                 # quotient
    li   x29, 0                 # remainder
    li   x30, 32                # one iteration per dividend bit

divrem_loop:
    beqz x30, divrem_apply_signs
    srli x5, x29, 31            # bit lost when the remainder shifts left
    srli x6, x10, 31            # next dividend bit, most significant first
    slli x29, x29, 1
    or   x29, x29, x6           # remainder = (remainder << 1) | bit
    slli x10, x10, 1
    slli x28, x28, 1
    bnez x5, divrem_subtract    # carry set: remainder is above any divisor
    bltu x29, x11, divrem_next
divrem_subtract:
    sub  x29, x29, x11
    ori  x28, x28, 1
divrem_next:
    addi x30, x30, -1
    j    divrem_loop

divrem_apply_signs:
    xor  x21, x19, x20          # quotient is negative when signs differ
    xor  x10, x28, x21
    sub  x10, x10, x21
    xor  x11, x29, x19          # remainder follows the dividend sign
    sub  x11, x11, x19
    ret

halt:
    j    halt                   # mandatory stop convention (ADR-003)
