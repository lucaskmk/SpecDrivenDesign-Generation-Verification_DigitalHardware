# bench_dotprod_rv32im.asm -- dot product of two vectors in RAM, RV32IM.
#
# REQ: FR-RV-12 (RV32IM extension), FR-RV-13 (MUL), FR-RV-17 (load/store,
#      loop and multiplication in the same pipeline, now with the M unit in
#      the execute stage), FR-RV-24 (cycle metrics against the RV32I version).
#
# Same algorithm, same vectors and same published results as
# bench_dotprod_rv32i.asm: only the inner multiplication changes, from a call
# to the 32-iteration shift-and-add routine to a single MUL in the loop body.
#
# Memory map:
#   0x00FC8100  results, slots 0..3
#   0x00FC8180  A[0..7]  (offset 128 from the base pointer)
#   0x00FC81A0  B[0..7]  (offset 160 from the base pointer)
#
# Register convention of this file:
#   x18  base pointer, 0x00FC8100
#   x19  loop index i
#   x20  dot product accumulator
#   x21  sum of A
#   x22  sum of B
#   x23  element count N
#   x24  address of the current element pair
#   x5   scratch used while initialising the vectors
#   x10, x11  current pair of elements
#   x12  product of the current pair

    li   x18, 0x00FC8100        # RESULT_BASE

    # ---- A = { 1, 2, 3, -4, 5, -6, 7, 100000 } ----------------------------
    li   x5, 1
    sw   x5, 128(x18)
    li   x5, 2
    sw   x5, 132(x18)
    li   x5, 3
    sw   x5, 136(x18)
    li   x5, -4
    sw   x5, 140(x18)
    li   x5, 5
    sw   x5, 144(x18)
    li   x5, -6
    sw   x5, 148(x18)
    li   x5, 7
    sw   x5, 152(x18)
    li   x5, 100000
    sw   x5, 156(x18)

    # ---- B = { 10, -20, 30, 40, 50, 60, 70, 100000 } ----------------------
    li   x5, 10
    sw   x5, 160(x18)
    li   x5, -20
    sw   x5, 164(x18)
    li   x5, 30
    sw   x5, 168(x18)
    li   x5, 40
    sw   x5, 172(x18)
    li   x5, 50
    sw   x5, 176(x18)
    li   x5, 60
    sw   x5, 180(x18)
    li   x5, 70
    sw   x5, 184(x18)
    li   x5, 100000
    sw   x5, 188(x18)

    # ---- multiply-accumulate loop ----------------------------------------
    li   x19, 0                 # i = 0
    li   x20, 0                 # dot = 0
    li   x21, 0                 # sum_a = 0
    li   x22, 0                 # sum_b = 0
    li   x23, 8                 # N = 8

dot_loop:
    beq  x19, x23, dot_store    # for (i = 0; i < N; i++)
    slli x24, x19, 2            # byte offset of element i
    add  x24, x24, x18
    lw   x10, 128(x24)          # A[i]
    lw   x11, 160(x24)          # B[i]
    add  x21, x21, x10          # sum_a += A[i]
    add  x22, x22, x11          # sum_b += B[i]
    mul  x12, x10, x11          # A[i] * B[i], low 32 bits, one cycle
    add  x20, x20, x12          # dot += product (modular 2^32)
    addi x19, x19, 1
    j    dot_loop

dot_store:
    sw   x20, 0(x18)            # slot 0 -- dot product
    sw   x21, 4(x18)            # slot 1 -- sum of A
    sw   x22, 8(x18)            # slot 2 -- sum of B
    sw   x23, 12(x18)           # slot 3 -- element count

halt:
    j    halt                   # mandatory stop convention (ADR-003)
