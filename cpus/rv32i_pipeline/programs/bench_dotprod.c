/*
 * bench_dotprod.c -- dot product of two small vectors held in data RAM
 *
 * REQ: FR-RV-18 (benchmark specified in C), FR-RV-13 (MUL), FR-RV-17
 *      (load/store, loop and multiplication exercised together, so the
 *      pipeline hazards show up), FR-RV-24 (efficiency comparison).
 *
 * WARNING -- THIS FILE IS NOT COMPILED IN THIS ENVIRONMENT.
 * No RISC-V C compiler exists here (verified by execution: no
 * riscv*-elf-gcc, no clang, no llvm-mc, neither on Windows nor on WSL).
 * See specs/decisions.md, ADR-004. This file is the readable specification
 * of the algorithm; the versioned translations actually assembled and run on
 * the CPU are:
 *     bench_dotprod_rv32i.asm   -- RV32I only, MUL emulated by shift-and-add
 *     bench_dotprod_rv32im.asm  -- RV32IM, one MUL inside the loop
 *
 * What it computes: the multiply-accumulate loop sum(A[i] * B[i]) over eight
 * elements, plus the two vector sums and the element count, so that a wrong
 * loop bound or a broken load shows up as a wrong checksum and not only as a
 * wrong product.
 *
 * Memory map. The CPU is a Harvard machine: the instruction ROM cannot be
 * read with `lw` and the data ROM is only 8 bytes wide, so both vectors live
 * in data RAM and are written there by the program itself before the loop.
 *     RESULT_BASE = 0x00FC8100   results, slots 0..3
 *     VEC_A       = 0x00FC8180   A[0..7], slots 32..39
 *     VEC_B       = 0x00FC81A0   B[0..7], slots 40..47
 *
 * A = { 1, 2, 3, -4, 5, -6, 7, 100000 }
 * B = { 10, -20, 30, 40, 50, 60, 70, 100000 }
 *
 * Expected results:
 *   slot 0  0x00FC8100  dot product   -> 1410065688  0x540BE518
 *   slot 1  0x00FC8104  sum of A      -> 100008      0x000186A8
 *   slot 2  0x00FC8108  sum of B      -> 100240      0x00018790
 *   slot 3  0x00FC810C  element count -> 8           0x00000008
 * The last pair, 100000 * 100000, overflows 32 bits, so the dot product is
 * the modular low word and not the mathematical 10^10 + 280.
 */

#define RESULT_BASE 0x00FC8100u
#define VEC_A       0x00FC8180u
#define VEC_B       0x00FC81A0u
#define N           8

/* RV32I emulation of MUL: shift-and-add, low 32 bits only. */
static unsigned int mul32(unsigned int a, unsigned int b)
{
    unsigned int product = 0u;

    while (b != 0u) {
        if (b & 1u) {
            product += a;
        }
        a <<= 1;
        b >>= 1;
    }
    return product;
}

void bench_dotprod(void)
{
    volatile unsigned int *out = (volatile unsigned int *)RESULT_BASE;
    volatile unsigned int *a = (volatile unsigned int *)VEC_A;
    volatile unsigned int *b = (volatile unsigned int *)VEC_B;
    unsigned int dot = 0u, sum_a = 0u, sum_b = 0u;
    int i;

    /* the vectors are materialised in RAM: there is no readable .rodata */
    a[0] = 1u;   a[1] = 2u;   a[2] = 3u;   a[3] = (unsigned int)-4;
    a[4] = 5u;   a[5] = (unsigned int)-6; a[6] = 7u; a[7] = 100000u;

    b[0] = 10u;  b[1] = (unsigned int)-20; b[2] = 30u; b[3] = 40u;
    b[4] = 50u;  b[5] = 60u; b[6] = 70u;  b[7] = 100000u;

    for (i = 0; i < N; i++) {
        unsigned int va = a[i];
        unsigned int vb = b[i];

        sum_a += va;
        sum_b += vb;
        dot += mul32(va, vb);   /* modular 2^32 accumulation */
    }

    out[0] = dot;
    out[1] = sum_a;
    out[2] = sum_b;
    out[3] = (unsigned int)N;
}
