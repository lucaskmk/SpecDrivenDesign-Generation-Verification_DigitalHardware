# bench_div_rv32im.asm -- division and remainder benchmark, RV32IM.
#
# REQ: FR-RV-12 (RV32IM extension), FR-RV-13 (DIV, REM), FR-RV-14 (special
#      cases handled by the hardware, not by software), FR-RV-22 (edge
#      operands), FR-RV-24 (cycle metrics against bench_div_rv32i.asm).
#
# Same algorithm and same published results as bench_div_rv32i.asm. The whole
# 32-iteration restoring-division routine collapses into one DIV plus one REM,
# and the two RISC-V special cases (divide by zero, INT32_MIN / -1) are now
# handled by mul_div_unit.vhd instead of by explicit branches.
#
# Slot layout: slot 2*i = quotient of case i, slot 2*i+1 = remainder.
#
# Register convention of this file:
#   x18       result area base pointer (RESULT_BASE = 0x00FC8100)
#   x10, x11  dividend and divisor
#   x12, x13  quotient and remainder

    li   x18, 0x00FC8100        # RESULT_BASE

    # case 0 -- 100 / 7, both positive
    li   x10, 100
    li   x11, 7
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 0(x18)
    sw   x13, 4(x18)

    # case 1 -- -100 / 7, negative dividend
    li   x10, -100
    li   x11, 7
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 8(x18)
    sw   x13, 12(x18)

    # case 2 -- 100 / -7, negative divisor
    li   x10, 100
    li   x11, -7
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 16(x18)
    sw   x13, 20(x18)

    # case 3 -- -100 / -7, both negative
    li   x10, -100
    li   x11, -7
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 24(x18)
    sw   x13, 28(x18)

    # case 4 -- 7 / 0, divide by zero: q = -1, r = dividend (FR-RV-14)
    li   x10, 7
    li   x11, 0
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 32(x18)
    sw   x13, 36(x18)

    # case 5 -- INT32_MIN / -1, signed overflow: q = INT32_MIN, r = 0
    li   x10, -2147483648
    li   x11, -1
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 40(x18)
    sw   x13, 44(x18)

    # case 6 -- INT32_MAX / 2
    li   x10, 2147483647
    li   x11, 2
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 48(x18)
    sw   x13, 52(x18)

    # case 7 -- INT32_MIN / 3, magnitude needs the full 32-bit unsigned range
    li   x10, -2147483648
    li   x11, 3
    div  x12, x10, x11
    rem  x13, x10, x11
    sw   x12, 56(x18)
    sw   x13, 60(x18)

halt:
    j    halt                   # mandatory stop convention (ADR-003)
