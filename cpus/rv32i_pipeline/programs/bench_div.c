/*
 * bench_div.c -- signed integer division and remainder benchmark
 *
 * REQ: FR-RV-18 (benchmark specified in C), FR-RV-13 (DIV, REM),
 *      FR-RV-14 (RISC-V special cases), FR-RV-22 (edge values),
 *      FR-RV-24 (RV32I vs RV32IM efficiency comparison).
 *
 * WARNING -- THIS FILE IS NOT COMPILED IN THIS ENVIRONMENT.
 * No RISC-V C compiler exists here (verified by execution: no
 * riscv*-elf-gcc, no clang, no llvm-mc, neither on Windows nor on WSL).
 * See specs/decisions.md, ADR-004. This file is the readable specification
 * of the algorithm; the versioned translations actually assembled and run on
 * the CPU are:
 *     bench_div_rv32i.asm   -- RV32I only, restoring division bit by bit
 *     bench_div_rv32im.asm  -- RV32IM, one DIV and one REM per case
 *
 * What it computes: quotient and remainder of eight (dividend, divisor)
 * pairs, following the RISC-V unprivileged specification exactly, including
 * the two special cases that do NOT trap:
 *     divisor == 0            -> quotient = -1, remainder = dividend
 *     -2^31 / -1 (overflow)   -> quotient = -2^31, remainder = 0
 * Division truncates towards zero and the remainder carries the sign of the
 * dividend.
 *
 * Slot layout, RESULT_BASE = 0x00FC8100: slot 2*i holds the quotient of case
 * i and slot 2*i+1 holds its remainder.
 *
 *   case 0  (100, 7)             q = 14           r = 2
 *   case 1  (-100, 7)            q = -14          r = -2
 *   case 2  (100, -7)            q = -14          r = 2
 *   case 3  (-100, -7)           q = 14           r = -2
 *   case 4  (7, 0)               q = -1           r = 7        (div by zero)
 *   case 5  (-2147483648, -1)    q = -2147483648  r = 0        (overflow)
 *   case 6  (2147483647, 2)      q = 1073741823   r = 1
 *   case 7  (-2147483648, 3)     q = -715827882   r = -2
 */

#define RESULT_BASE 0x00FC8100u

#define INT32_MIN_U 0x80000000u

/*
 * RV32I emulation: restoring division, 32 iterations, unsigned operands.
 * `carry` is the bit that would be lost when the 32-bit partial remainder is
 * shifted left; when it is set the partial remainder is already larger than
 * any 32-bit divisor, so the subtraction must happen unconditionally. Without
 * it, divisors >= 2^31 would give wrong results.
 */
static void udivmod32(unsigned int n, unsigned int d,
                      unsigned int *q_out, unsigned int *r_out)
{
    unsigned int q = 0u;
    unsigned int r = 0u;
    int i;

    for (i = 0; i < 32; i++) {
        unsigned int carry = r >> 31;

        r = (r << 1) | (n >> 31);
        n <<= 1;
        q <<= 1;
        if (carry != 0u || r >= d) {
            r -= d;
            q |= 1u;
        }
    }
    *q_out = q;
    *r_out = r;
}

/* Signed DIV/REM with the exact RISC-V semantics, built on udivmod32(). */
static void divrem32(unsigned int a, unsigned int b,
                     unsigned int *q_out, unsigned int *r_out)
{
    unsigned int sign_a, sign_b, ua, ub, q, r;

    if (b == 0u) {                          /* FR-RV-14: divide by zero */
        *q_out = 0xFFFFFFFFu;               /* -1                       */
        *r_out = a;                         /* dividend unchanged       */
        return;
    }
    if (a == INT32_MIN_U && b == 0xFFFFFFFFu) {   /* FR-RV-14: overflow */
        *q_out = INT32_MIN_U;
        *r_out = 0u;
        return;
    }

    sign_a = (unsigned int)((int)a >> 31);  /* 0xFFFFFFFF when negative */
    sign_b = (unsigned int)((int)b >> 31);
    ua = (a ^ sign_a) - sign_a;             /* absolute value           */
    ub = (b ^ sign_b) - sign_b;

    udivmod32(ua, ub, &q, &r);

    q = (q ^ (sign_a ^ sign_b)) - (sign_a ^ sign_b);  /* quotient sign  */
    r = (r ^ sign_a) - sign_a;                        /* dividend sign  */

    *q_out = q;
    *r_out = r;
}

void bench_div(void)
{
    volatile unsigned int *out = (volatile unsigned int *)RESULT_BASE;
    unsigned int q, r;

    divrem32(100u, 7u, &q, &r);              out[0]  = q; out[1]  = r;
    divrem32((unsigned int)-100, 7u, &q, &r); out[2] = q; out[3]  = r;
    divrem32(100u, (unsigned int)-7, &q, &r); out[4] = q; out[5]  = r;
    divrem32((unsigned int)-100,
             (unsigned int)-7, &q, &r);       out[6] = q; out[7]  = r;
    divrem32(7u, 0u, &q, &r);                 out[8] = q; out[9]  = r;
    divrem32(INT32_MIN_U, 0xFFFFFFFFu,
             &q, &r);                         out[10] = q; out[11] = r;
    divrem32(2147483647u, 2u, &q, &r);        out[12] = q; out[13] = r;
    divrem32(INT32_MIN_U, 3u, &q, &r);        out[14] = q; out[15] = r;
}
