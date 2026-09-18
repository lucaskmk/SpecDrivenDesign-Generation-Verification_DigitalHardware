# bench_mul_rv32im.asm -- integer multiplication benchmark, RV32IM.
#
# REQ: FR-RV-12 (RV32IM extension), FR-RV-13 (MUL), FR-RV-22 (edge operands),
#      FR-RV-24 (cycle metrics compared against bench_mul_rv32i.asm).
#
# Same algorithm and same published results as bench_mul_rv32i.asm: only the
# multiplication changes, from the 32-iteration shift-and-add loop to a single
# MUL instruction, which in this design is combinational and therefore costs
# the same one cycle as an ALU operation (ADR-007).
#
# Register convention of this file:
#   x18  result area base pointer (RESULT_BASE = 0x00FC8100)
#   x10, x11  operands
#   x12  product

    li   x18, 0x00FC8100        # RESULT_BASE

    # slot 0 -- 7 * 6, small positive operands
    li   x10, 7
    li   x11, 6
    mul  x12, x10, x11
    sw   x12, 0(x18)

    # slot 1 -- 123 * 456, still fits in 32 bits
    li   x10, 123
    li   x11, 456
    mul  x12, x10, x11
    sw   x12, 4(x18)

    # slot 2 -- -3 * 5, mixed signs
    li   x10, -3
    li   x11, 5
    mul  x12, x10, x11
    sw   x12, 8(x18)

    # slot 3 -- -7 * -8, both operands negative
    li   x10, -7
    li   x11, -8
    mul  x12, x10, x11
    sw   x12, 12(x18)

    # slot 4 -- 65535 * 65537, the largest product that still fits: 2^32-1
    li   x10, 65535
    li   x11, 65537
    mul  x12, x10, x11
    sw   x12, 16(x18)

    # slot 5 -- INT32_MAX * 2, overflows 32 bits
    li   x10, 2147483647
    li   x11, 2
    mul  x12, x10, x11
    sw   x12, 20(x18)

    # slot 6 -- INT32_MIN * 3, overflows 32 bits
    li   x10, -2147483648
    li   x11, 3
    mul  x12, x10, x11
    sw   x12, 24(x18)

    # slot 7 -- 0 * 0x12345678, zero operand
    li   x10, 0
    li   x11, 305419896
    mul  x12, x10, x11
    sw   x12, 28(x18)

halt:
    j    halt                   # mandatory stop convention (ADR-003)
