/* Minimal RV32I test environment for the upstream riscv-tests ISA sources.
 * Unlike riscv-tests/env/p it does not execute CSR setup or ECALL. */
#ifndef SPEC_RISCV_TEST_ENV_H
#define SPEC_RISCV_TEST_ENV_H

#define RVTEST_RV32U .macro init; .endm
#define RVTEST_RV64U RVTEST_RV32U
#define TESTNUM gp

#define RVTEST_CODE_BEGIN \
  .section .text.init; .align 2; .globl _start; _start:; \
  li x1, 0; li x2, 0; li x3, 0; li x4, 0; li x5, 0; li x6, 0; li x7, 0; \
  li x8, 0; li x9, 0; li x10, 0; li x11, 0; li x12, 0; li x13, 0; li x14, 0; \
  li x15, 0; li x16, 0; li x17, 0; li x18, 0; li x19, 0; li x20, 0; li x21, 0; \
  li x22, 0; li x23, 0; li x24, 0; li x25, 0; li x26, 0; li x27, 0; li x28, 0; \
  li x29, 0; li x30, 0; li x31, 0; init;

#define RVTEST_PASS \
  li TESTNUM, 1; la t0, tohost; sw TESTNUM, 0(t0); 1: j 1b

#define RVTEST_FAIL \
  slli TESTNUM, TESTNUM, 1; ori TESTNUM, TESTNUM, 1; la t0, tohost; \
  sw TESTNUM, 0(t0); 1: j 1b

#define RVTEST_CODE_END 1: j 1b
#define RVTEST_DATA_BEGIN \
  .pushsection .tohost,"aw",@progbits; .align 2; .global tohost; tohost: .word 0; \
  .popsection; .align 4; .global begin_signature; begin_signature:
#define RVTEST_DATA_END .align 4; .global end_signature; end_signature:
#endif
