/*
 * bench_signs.c -- signed/unsigned edge values and modular 32-bit overflow
 *
 * REQ: FR-RV-18 (benchmark specified in C), FR-RV-22 (edge values, including
 *      -2^31 and 2^31-1), FR-RV-13 (MUL on those values), FR-RV-24.
 *
 * WARNING -- THIS FILE IS NOT COMPILED IN THIS ENVIRONMENT.
 * No RISC-V C compiler exists here (verified by execution: no
 * riscv*-elf-gcc, no clang, no llvm-mc, neither on Windows nor on WSL).
 * See specs/decisions.md, ADR-004. This file is the readable specification
 * of the algorithm; the versioned translations actually assembled and run on
 * the CPU are:
 *     bench_signs_rv32i.asm   -- RV32I only, MUL emulated by shift-and-add
 *     bench_signs_rv32im.asm  -- RV32IM, one MUL per multiplication
 *
 * What it computes: the behaviour of the two extremes of the signed 32-bit
 * range under addition, subtraction, multiplication, signed and unsigned
 * comparison, and the two shift-right flavours. Everything is modular in
 * 2^32: there is no saturation and no trap anywhere.
 *
 * Expected result per RAM slot, RESULT_BASE = 0x00FC8100:
 *   slot  0  0x00FC8100  INT32_MAX + 1            -> 0x80000000  (wraps)
 *   slot  1  0x00FC8104  INT32_MIN + (-1)         -> 0x7FFFFFFF  (wraps)
 *   slot  2  0x00FC8108  0 - INT32_MIN            -> 0x80000000  (no +2^31)
 *   slot  3  0x00FC810C  INT32_MIN * -1           -> 0x80000000
 *   slot  4  0x00FC8110  INT32_MAX * 2            -> 0xFFFFFFFE
 *   slot  5  0x00FC8114  INT32_MIN * INT32_MIN    -> 0x00000000
 *   slot  6  0x00FC8118  INT32_MAX * INT32_MAX    -> 0x00000001
 *   slot  7  0x00FC811C  INT32_MIN <  INT32_MAX   -> 1  (signed)
 *   slot  8  0x00FC8120  INT32_MIN <u INT32_MAX   -> 0  (unsigned)
 *   slot  9  0x00FC8124  INT32_MIN >> 31 (arith)  -> 0xFFFFFFFF
 *   slot 10  0x00FC8128  INT32_MIN >> 31 (logic)  -> 0x00000001
 *   slot 11  0x00FC812C  (-1) * (-1)              -> 0x00000001
 */

#define RESULT_BASE 0x00FC8100u

#define INT32_MAX_U 0x7FFFFFFFu
#define INT32_MIN_U 0x80000000u

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

void bench_signs(void)
{
    volatile unsigned int *out = (volatile unsigned int *)RESULT_BASE;
    unsigned int hi = INT32_MAX_U;
    unsigned int lo = INT32_MIN_U;

    out[0]  = hi + 1u;                          /* modular overflow      */
    out[1]  = lo + 0xFFFFFFFFu;                 /* modular underflow     */
    out[2]  = 0u - lo;                          /* -INT32_MIN == itself  */
    out[3]  = mul32(lo, 0xFFFFFFFFu);           /* INT32_MIN * -1        */
    out[4]  = mul32(hi, 2u);                    /* INT32_MAX * 2         */
    out[5]  = mul32(lo, lo);                    /* 2^62 mod 2^32 == 0    */
    out[6]  = mul32(hi, hi);                    /* (2^31-1)^2 mod 2^32   */
    out[7]  = ((int)lo < (int)hi) ? 1u : 0u;    /* signed compare        */
    out[8]  = (lo < hi) ? 1u : 0u;              /* unsigned compare      */
    out[9]  = (unsigned int)((int)lo >> 31);    /* arithmetic shift      */
    out[10] = lo >> 31;                         /* logical shift         */
    out[11] = mul32(0xFFFFFFFFu, 0xFFFFFFFFu);  /* (-1) * (-1)           */
}
