/*
 * bench_mul.c -- integer multiplication benchmark (low 32 bits of the product)
 *
 * REQ: FR-RV-18 (benchmark specified in C), FR-RV-13 (MUL), FR-RV-22 (edge
 *      values), FR-RV-24 (RV32I vs RV32IM efficiency comparison).
 *
 * WARNING -- THIS FILE IS NOT COMPILED IN THIS ENVIRONMENT.
 * No RISC-V C compiler exists here (verified by execution: no
 * riscv*-elf-gcc, no clang, no llvm-mc, neither on Windows nor on WSL).
 * See specs/decisions.md, ADR-004. This file is the readable specification
 * of the algorithm; the versioned translations actually assembled and run on
 * the CPU are:
 *     bench_mul_rv32i.asm   -- RV32I only, MUL emulated by shift-and-add
 *     bench_mul_rv32im.asm  -- RV32IM, one MUL instruction per case
 *
 * What it computes: the low 32 bits of a * b for eight operand pairs chosen
 * to cover zero, small positives, mixed signs, both negatives and modular
 * 2^32 overflow. The low 32 bits of a product are identical for the signed
 * and the unsigned interpretation of the operands, which is exactly what
 * RISC-V MUL defines, so both versions must publish the same words.
 *
 * Inputs (a, b) and expected result per RAM slot, RESULT_BASE = 0x00FC8100:
 *   slot 0  0x00FC8100  7 * 6                      -> 42          0x0000002A
 *   slot 1  0x00FC8104  123 * 456                  -> 56088       0x0000DB18
 *   slot 2  0x00FC8108  -3 * 5                     -> -15         0xFFFFFFF1
 *   slot 3  0x00FC810C  -7 * -8                    -> 56          0x00000038
 *   slot 4  0x00FC8110  65535 * 65537              -> 4294967295  0xFFFFFFFF
 *   slot 5  0x00FC8114  2147483647 * 2             -> -2          0xFFFFFFFE
 *   slot 6  0x00FC8118  -2147483648 * 3            -> -2147483648 0x80000000
 *   slot 7  0x00FC811C  0 * 305419896              -> 0           0x00000000
 * Slot 4 is the largest product that still fits in 32 bits, exactly
 * 2^32 - 1. Slots 5 and 6 do overflow, so their result is the modular low
 * word and not the mathematical product.
 */

#define RESULT_BASE 0x00FC8100u

/*
 * RV32I emulation of MUL: shift-and-add, low 32 bits only.
 * Terminates after at most 32 iterations because b is shifted right
 * logically, so it always reaches zero.
 */
static unsigned int mul32(unsigned int a, unsigned int b)
{
    unsigned int product = 0u;

    while (b != 0u) {
        if (b & 1u) {
            product += a;           /* modular 2^32, no saturation */
        }
        a <<= 1;
        b >>= 1;
    }
    return product;
}

void bench_mul(void)
{
    volatile unsigned int *out = (volatile unsigned int *)RESULT_BASE;

    out[0] = mul32(7u, 6u);                     /* small positives      */
    out[1] = mul32(123u, 456u);                 /* still fits in 32 bit */
    out[2] = mul32((unsigned int)-3, 5u);       /* mixed signs          */
    out[3] = mul32((unsigned int)-7,
                   (unsigned int)-8);           /* both negative        */
    out[4] = mul32(65535u, 65537u);             /* exactly 2^32 - 1     */
    out[5] = mul32(2147483647u, 2u);            /* INT32_MAX * 2        */
    out[6] = mul32(2147483648u, 3u);            /* INT32_MIN * 3        */
    out[7] = mul32(0u, 305419896u);             /* zero operand         */
}
