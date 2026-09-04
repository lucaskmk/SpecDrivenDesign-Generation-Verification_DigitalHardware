/* =============================================================================
 * examples/riscv_base_test/src/program.S
 * Mandatory RV32I base test program -- GOLDEN FIXTURE (pipeline:FR-18)
 *
 * Written by hand in assembly, not compiled from C: coverage has to be
 * instruction by instruction (pipeline:FR-26) and with C the compiler decides
 * what gets emitted (specs/plan.md, phase 3b).
 *
 * Contract of this fixture (specs/plan.md, "Regras do programa de teste"):
 *   1. every declared RV32I instruction is executed, and each one writes its
 *      result to a distinct, known RAM address;
 *   2. operands come from registers loaded at run time, never from something
 *      the assembler could fold;
 *   3. the program ends by writing the sentinel and entering an infinite
 *      loop, so the testbench can tell "finished" from "hung" (FR-28);
 *   4. it must include, explicitly: call/return (jal/jalr), saving and
 *      restoring registers on the stack, and reading a .rodata constant
 *      through auipc/lui + offset.
 *
 * Memory map (CPU-independent part of the contract):
 *   ROM  0x00000000 .. 0x00000FFF   .text + .rodata
 *   RAM  0x00FC8000 .. 0x00FC8FFF   results, scratch, stack
 *   results   x3 + 0x000 .. 0x097
 *   scratch   x3 + 0x100 .. 0x107
 *   stack top       0x00FC8FF0 (grows down)
 *   sentinel        0x00FC8FFC = 0xC0FFEE00
 *
 * Fixed register allocation (loaded once, never clobbered):
 *   x1  ra                      x2  sp = 0x00FC8FF0
 *   x3  RAM base = 0x00FC8000   x4  100
 *   x5  23                      x6  0xF0F0F0F0 (negative)
 *   x7  0xFF00F00F              x8  -1
 *   x9  4 (shift amount)        x10..x31 temporaries
 * =========================================================================== */

    .section .text
    .globl _start

_start:
    /* ---------------------------------------------------------------------
     * Base pointer, stack pointer and the constant pool -- lui / addi
     * ------------------------------------------------------------------- */
    lui   x3, 0xFC8             /* x3 = 0x00FC8000                  [lui]  */
    lui   x2, 0xFC9
    addi  x2, x2, -16           /* sp = 0x00FC8FF0                  [addi] */

    addi  x4, x0, 100           /* A = 100                                 */
    addi  x5, x0, 23            /* B = 23                                  */
    lui   x6, 0xF0F0F
    addi  x6, x6, 0xF0          /* P = 0xF0F0F0F0                          */
    lui   x7, 0xFF00F
    addi  x7, x7, 0x0F          /* Q = 0xFF00F00F                          */
    addi  x8, x0, -1            /* 0xFFFFFFFF                              */
    addi  x9, x0, 4             /* shift amount                            */

    /* [0x00] lui: the base pointer itself is the evidence, stored with sw  */
    sw    x3, 0x00(x3)          /*                                   [sw]  */
    /* [0x04] addi                                                          */
    sw    x4, 0x04(x3)

    /* ---------------------------------------------------------------------
     * Register/register arithmetic and logic
     * ------------------------------------------------------------------- */
    add   x10, x4, x5           /* 100 + 23 = 123                   [add]  */
    sw    x10, 0x08(x3)
    sub   x11, x4, x5           /* 100 - 23 = 77                    [sub]  */
    sw    x11, 0x0C(x3)
    and   x12, x6, x7           /* 0xF000F000                       [and]  */
    sw    x12, 0x10(x3)
    or    x13, x6, x7           /* 0xFFF0F0FF                       [or]   */
    sw    x13, 0x14(x3)
    xor   x14, x6, x7           /* 0x0FF000FF                       [xor]  */
    sw    x14, 0x18(x3)
    sll   x15, x4, x9           /* 100 << 4 = 1600                  [sll]  */
    sw    x15, 0x1C(x3)
    srl   x16, x6, x9           /* 0x0F0F0F0F                       [srl]  */
    sw    x16, 0x20(x3)
    sra   x17, x6, x9           /* 0xFF0F0F0F                       [sra]  */
    sw    x17, 0x24(x3)
    slt   x18, x6, x4           /* signed: negative < 100 -> 1      [slt]  */
    sw    x18, 0x28(x3)
    sltu  x19, x6, x4           /* unsigned: huge < 100 -> 0        [sltu] */
    sw    x19, 0x2C(x3)

    /* ---------------------------------------------------------------------
     * Immediate arithmetic and logic
     * ------------------------------------------------------------------- */
    slti  x20, x5, -1           /* signed: 23 < -1 -> 0            [slti]  */
    sw    x20, 0x30(x3)
    sltiu x21, x5, -1           /* unsigned: 23 < 0xFFFFFFFF -> 1  [sltiu] */
    sw    x21, 0x34(x3)
    xori  x22, x6, -1           /* ~P = 0x0F0F0F0F                 [xori]  */
    sw    x22, 0x38(x3)
    ori   x23, x4, 0x0F         /* 0x64 | 0x0F = 0x6F              [ori]   */
    sw    x23, 0x3C(x3)
    andi  x24, x4, 0x0F         /* 0x64 & 0x0F = 0x04              [andi]  */
    sw    x24, 0x40(x3)
    slli  x25, x4, 5            /* 100 << 5 = 3200                 [slli]  */
    sw    x25, 0x44(x3)
    srli  x26, x6, 8            /* 0x00F0F0F0                      [srli]  */
    sw    x26, 0x48(x3)
    srai  x27, x6, 8            /* 0xFFF0F0F0                      [srai]  */
    sw    x27, 0x4C(x3)

    /* ---------------------------------------------------------------------
     * auipc -- checked in a layout-independent way: the difference between
     * two auipc results only depends on PC arithmetic and on imm << 12, so
     * the expected value does not move if the program grows.
     * ------------------------------------------------------------------- */
    auipc x28, 0                /* x28 = pc_here                  [auipc]  */
    auipc x29, 1                /* x29 = pc_here + 4 + 0x1000              */
    sub   x30, x29, x28         /* = 0x00001004                            */
    sw    x30, 0x50(x3)

    /* ---------------------------------------------------------------------
     * .rodata reads -- mandatory in this fixture (specs/plan.md, phase 3b)
     * ------------------------------------------------------------------- */
    /* PC-relative, through auipc + lw */
1:  auipc x10, %pcrel_hi(const_a)
    lw    x11, %pcrel_lo(1b)(x10)   /* 0xA5A5A5A5                  [lw]    */
    sw    x11, 0x54(x3)
    /* absolute, through lui + lw */
    lui   x12, %hi(const_b)
    lw    x13, %lo(const_b)(x12)    /* 0x5A5A0001                  [lw]    */
    sw    x13, 0x58(x3)

    /* ---------------------------------------------------------------------
     * Byte and halfword stores, then loads back with both extensions
     * scratch: [0x100] built with sb, [0x104] built with sh
     * ------------------------------------------------------------------- */
    sw    x0, 0x100(x3)         /* clear the scratch word                  */
    addi  x14, x0, 0x12
    sb    x14, 0x100(x3)        /*                                  [sb]   */
    addi  x14, x0, 0x34
    sb    x14, 0x101(x3)
    addi  x14, x0, 0x56
    sb    x14, 0x102(x3)
    addi  x14, x0, 0x78
    sb    x14, 0x103(x3)
    lw    x15, 0x100(x3)        /* little-endian -> 0x78563412             */
    sw    x15, 0x5C(x3)

    sw    x0, 0x104(x3)
    lui   x16, 0x8
    addi  x16, x16, 1           /* 0x00008001                              */
    lui   x17, 0x8
    addi  x17, x17, -1          /* 0x00007FFF                              */
    sh    x16, 0x104(x3)        /* low half  = 0x8001               [sh]   */
    sh    x17, 0x106(x3)        /* high half = 0x7FFF                      */
    lw    x18, 0x104(x3)        /* 0x7FFF8001                              */
    sw    x18, 0x60(x3)

    lb    x19, 0x105(x3)        /* byte 0x80 sign extended          [lb]   */
    sw    x19, 0x64(x3)
    lbu   x20, 0x105(x3)        /* byte 0x80 zero extended          [lbu]  */
    sw    x20, 0x68(x3)
    lh    x21, 0x104(x3)        /* half 0x8001 sign extended        [lh]   */
    sw    x21, 0x6C(x3)
    lhu   x22, 0x104(x3)        /* half 0x8001 zero extended        [lhu]  */
    sw    x22, 0x70(x3)

    /* ---------------------------------------------------------------------
     * Conditional branches. Each branch is exercised twice: once where it
     * must be taken (+1) and once where it must fall through (+2), so the
     * expected value 3 pins down *both* directions. A wrong decision in
     * either direction lands on 8/9/1 instead.
     * ------------------------------------------------------------------- */
    /* beq */
    addi  x23, x0, 0
    beq   x4, x4, 1f            /* taken                            [beq]  */
    addi  x23, x23, 8
1:  addi  x23, x23, 1
    beq   x4, x5, 2f            /* not taken                               */
    addi  x23, x23, 2
2:  sw    x23, 0x74(x3)

    /* bne */
    addi  x23, x0, 0
    bne   x4, x5, 1f            /* taken                            [bne]  */
    addi  x23, x23, 8
1:  addi  x23, x23, 1
    bne   x4, x4, 2f            /* not taken                               */
    addi  x23, x23, 2
2:  sw    x23, 0x78(x3)

    /* blt (signed) */
    addi  x23, x0, 0
    blt   x6, x4, 1f            /* negative < 100 -> taken          [blt]  */
    addi  x23, x23, 8
1:  addi  x23, x23, 1
    blt   x4, x6, 2f            /* 100 < negative -> not taken             */
    addi  x23, x23, 2
2:  sw    x23, 0x7C(x3)

    /* bge (signed) */
    addi  x23, x0, 0
    bge   x4, x6, 1f            /* 100 >= negative -> taken         [bge]  */
    addi  x23, x23, 8
1:  addi  x23, x23, 1
    bge   x6, x4, 2f            /* negative >= 100 -> not taken            */
    addi  x23, x23, 2
2:  sw    x23, 0x80(x3)

    /* bltu (unsigned) */
    addi  x23, x0, 0
    bltu  x5, x4, 1f            /* 23 <u 100 -> taken               [bltu] */
    addi  x23, x23, 8
1:  addi  x23, x23, 1
    bltu  x6, x4, 2f            /* 0xF0F0F0F0 <u 100 -> not taken          */
    addi  x23, x23, 2
2:  sw    x23, 0x84(x3)

    /* bgeu (unsigned) */
    addi  x23, x0, 0
    bgeu  x6, x4, 1f            /* 0xF0F0F0F0 >=u 100 -> taken      [bgeu] */
    addi  x23, x23, 8
1:  addi  x23, x23, 1
    bgeu  x5, x4, 2f            /* 23 >=u 100 -> not taken                 */
    addi  x23, x23, 2
2:  sw    x23, 0x88(x3)

    /* ---------------------------------------------------------------------
     * Call and return, with the callee saving x1/x18 on the stack.
     * add_double(a, b) = (a + b) * 2, arguments in x10/x11, result in x10.
     * x18 is loaded with a witness value before the call: if the callee's
     * save/restore is broken, [0x94] shows it.
     * ------------------------------------------------------------------- */
    addi  x18, x0, 0x777        /* witness in a callee-saved register      */

    /* direct call */
    addi  x10, x0, 10
    addi  x11, x0, 4
    jal   x1, add_double        /* (10+4)*2 = 28                    [jal]  */
    sw    x10, 0x8C(x3)

    /* indirect call through a register target */
    lui   x12, %hi(add_double)
    addi  x12, x12, %lo(add_double)
    addi  x10, x0, 7
    addi  x11, x0, 5
    jalr  x1, 0(x12)            /* (7+5)*2 = 24                     [jalr] */
    sw    x10, 0x90(x3)

    /* the witness survived both calls -> stack save/restore works */
    sw    x18, 0x94(x3)

    /* ---------------------------------------------------------------------
     * Termination: sentinel then infinite loop (FR-28)
     * ------------------------------------------------------------------- */
    lui   x13, 0xFC9
    addi  x13, x13, -4          /* 0x00FC8FFC                              */
    lui   x14, 0xC0FFF
    addi  x14, x14, -512        /* 0xC0FFEE00                              */
    sw    x14, 0(x13)
done:
    jal   x0, done              /* spin forever                            */

/* -----------------------------------------------------------------------------
 * add_double: uses the stack, clobbers and restores a callee-saved register,
 * and returns with jalr.
 * -------------------------------------------------------------------------- */
add_double:
    addi  x2, x2, -16           /* prologue                                */
    sw    x1, 12(x2)            /* save return address                     */
    sw    x18, 8(x2)            /* save callee-saved register              */
    add   x18, x10, x11
    add   x10, x18, x18
    addi  x18, x0, 0            /* deliberately clobber before restoring   */
    lw    x18, 8(x2)            /* restore                                 */
    lw    x1, 12(x2)
    addi  x2, x2, 16            /* epilogue                                */
    jalr  x0, 0(x1)             /* return                           [jalr] */

    .section .rodata
    .align 2
const_a:
    .word 0xA5A5A5A5
const_b:
    .word 0x5A5A0001
