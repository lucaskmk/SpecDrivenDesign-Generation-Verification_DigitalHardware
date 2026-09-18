/* =============================================================================
 * software/ext_m_test/src/program.S
 * Test program of the standard M extension -- REQ: FR-04, FR-11
 * (pipeline:FR-19)
 *
 * One program per extension (specs/plan.md, phase 3b): this one exercises all
 * 8 instructions that M adds -- mul, mulh, mulhsu, mulhu, div, divu, rem,
 * remu -- plus every edge case FR-11 pins down (division by zero and the
 * -2^31 / -1 overflow).
 *
 * Written directly in assembly, not compiled from C: with C the compiler picks
 * the instructions and coverage stops being controllable (pipeline:FR-26).
 *
 * Operand choice is deliberate. Every 64-bit product here is a power of two
 * (or a small multiple of one), so the expected value of mulh/mulhu/mulhsu can
 * be derived by hand with no 64-bit long multiplication -- the oracle in
 * expected_ram.json has to be verifiable by a human reading it.
 *
 * The four multiply-high variants are exercised on 0xFFFFFFFF x 0x80000000,
 * where all four answers differ:
 *     mul    -> 0x80000000   (low word)
 *     mulh   -> 0x00000000   (signed  x signed:   -1 * -2^31 = +2^31)
 *     mulhu  -> 0x7FFFFFFF   (unsigned x unsigned: (2^32-1) * 2^31)
 *     mulhsu -> 0xFFFFFFFF   (signed  x unsigned: -1 * 2^31 = -2^31)
 * A CPU that wires the wrong signedness into the multiplier cannot pass all
 * four at once.
 *
 * Memory map (same contract as the base test):
 *   ROM  0x00000000 .. 0x00000FFF   .text
 *   RAM  0x00FC8000 .. 0x00FC8FFF   results at x3 + 0x00 .. 0x5F
 *   sentinel  0x00FC8FFC = 0xC0FFEE00
 *
 * Fixed operand registers (loaded once, never clobbered):
 *   x3  RAM base 0x00FC8000     x4  0x12345678
 *   x5  16                      x6  0x00010001
 *   x7  0xFFFFFFFF (-1)         x8  0x80000000 (-2^31)
 *   x9  0x40000000 (+2^30)      x10 0xC0000000 (-2^30)
 *   x11 100                     x12 7
 *   x13 -100                    x14 -7
 *   x15 result temp             x0  the zero divisor of the FR-11 cases
 * =========================================================================== */

    .section .text
    .globl _start

_start:
    lui    x3, 0xFC8            /* RAM base = 0x00FC8000                   */
    lui    x2, 0xFC9
    addi   x2, x2, -16          /* sp = 0x00FC8FF0 (unused, kept uniform)  */

    /* ---------------------------------------------------------------------
     * Operand pool. Built at run time from lui/addi so the assembler cannot
     * constant-fold any of the M results.
     * ------------------------------------------------------------------- */
    lui    x4, 0x12345
    addi   x4, x4, 0x678        /* 0x12345678                              */
    addi   x5, x0, 16
    lui    x6, 0x10
    addi   x6, x6, 1            /* 0x00010001 = 65537                      */
    addi   x7, x0, -1           /* 0xFFFFFFFF                              */
    lui    x8, 0x80000          /* 0x80000000 = -2^31                      */
    lui    x9, 0x40000          /* 0x40000000 = +2^30                      */
    lui    x10, 0xC0000         /* 0xC0000000 = -2^30                      */
    addi   x11, x0, 100
    addi   x12, x0, 7
    addi   x13, x0, -100
    addi   x14, x0, -7

    /* ---------------------------------------------------------------------
     * mul -- low 32 bits of the product
     * ------------------------------------------------------------------- */
    mul    x15, x4, x5          /* 0x12345678 * 16, shifted out of range   */
    sw     x15, 0x00(x3)
    mul    x15, x6, x6          /* 65537^2 wraps past 32 bits              */
    sw     x15, 0x04(x3)
    mul    x15, x7, x8          /* -1 * -2^31, low word only               */
    sw     x15, 0x08(x3)

    /* ---------------------------------------------------------------------
     * mulh -- high 32 bits, signed x signed
     * ------------------------------------------------------------------- */
    mulh   x15, x9, x9          /* (+2^30)^2 = 2^60                        */
    sw     x15, 0x0C(x3)
    mulh   x15, x10, x10        /* (-2^30)^2 = 2^60 (two negatives)        */
    sw     x15, 0x10(x3)
    mulh   x15, x7, x8          /* -1 * -2^31 = +2^31                      */
    sw     x15, 0x14(x3)

    /* ---------------------------------------------------------------------
     * mulhu -- high 32 bits, unsigned x unsigned
     * ------------------------------------------------------------------- */
    mulhu  x15, x10, x10        /* (3*2^30)^2 = 9*2^60, differs from mulh  */
    sw     x15, 0x18(x3)
    mulhu  x15, x7, x8          /* (2^32-1) * 2^31                         */
    sw     x15, 0x1C(x3)

    /* ---------------------------------------------------------------------
     * mulhsu -- high 32 bits, signed rs1 x unsigned rs2
     * ------------------------------------------------------------------- */
    mulhsu x15, x7, x8          /* -1 * 2^31 = -2^31                       */
    sw     x15, 0x20(x3)
    mulhsu x15, x9, x10         /* +2^30 * 3*2^30 = 3*2^60                 */
    sw     x15, 0x24(x3)

    /* ---------------------------------------------------------------------
     * div -- signed, truncating toward zero
     * ------------------------------------------------------------------- */
    div    x15, x7, x5          /* -1 / 16 -> 0 (toward zero, not -1)      */
    sw     x15, 0x28(x3)
    div    x15, x13, x12        /* -100 / 7 -> -14                         */
    sw     x15, 0x2C(x3)
    div    x15, x11, x14        /* 100 / -7 -> -14                         */
    sw     x15, 0x30(x3)
    div    x15, x11, x0         /* FR-11: divisor 0 -> -1                  */
    sw     x15, 0x34(x3)
    div    x15, x8, x7          /* FR-11: -2^31 / -1 -> -2^31 (overflow)   */
    sw     x15, 0x38(x3)

    /* ---------------------------------------------------------------------
     * divu -- unsigned
     * ------------------------------------------------------------------- */
    divu   x15, x7, x5          /* 0xFFFFFFFF / 16, unsigned this time     */
    sw     x15, 0x3C(x3)
    divu   x15, x11, x0         /* FR-11: divisor 0 -> 0xFFFFFFFF          */
    sw     x15, 0x40(x3)

    /* ---------------------------------------------------------------------
     * rem -- signed, sign follows the dividend
     * ------------------------------------------------------------------- */
    rem    x15, x7, x5          /* -1 % 16 -> -1                           */
    sw     x15, 0x44(x3)
    rem    x15, x13, x12        /* -100 % 7 -> -2                          */
    sw     x15, 0x48(x3)
    rem    x15, x11, x14        /* 100 % -7 -> +2                          */
    sw     x15, 0x4C(x3)
    rem    x15, x11, x0         /* FR-11: divisor 0 -> dividend            */
    sw     x15, 0x50(x3)
    rem    x15, x8, x7          /* FR-11: -2^31 % -1 -> 0 (overflow)       */
    sw     x15, 0x54(x3)

    /* ---------------------------------------------------------------------
     * remu -- unsigned
     * ------------------------------------------------------------------- */
    remu   x15, x7, x5          /* 0xFFFFFFFF % 16 -> 15                   */
    sw     x15, 0x58(x3)
    remu   x15, x11, x0         /* FR-11: divisor 0 -> dividend            */
    sw     x15, 0x5C(x3)

    /* ---------------------------------------------------------------------
     * Termination: sentinel then infinite loop (pipeline:FR-28)
     * ------------------------------------------------------------------- */
    lui    x28, 0xFC9
    addi   x28, x28, -4         /* 0x00FC8FFC                              */
    lui    x29, 0xC0FFF
    addi   x29, x29, -512       /* 0xC0FFEE00                              */
    sw     x29, 0(x28)
done:
    jal    x0, done             /* spin forever                            */
