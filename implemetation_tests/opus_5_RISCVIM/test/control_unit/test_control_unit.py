#!/usr/bin/env python3
"""Testbench of the hardwired control unit.

# REQ: FR-03, FR-04, FR-05, FR-14

Every one of the 45 declared instructions is encoded by test/lib/riscv_isa.py
(from the RISC-V format tables) and the resulting control word is compared
against the decode contract of spec.md. The second half of the file is the
FR-14 side: instructions that are explicitly out of scope, plus reserved
funct3/funct7 encodings, must raise `illegal` and, crucially, must not write
a register or memory -- an unimplemented opcode aliasing onto an implemented
one is exactly how coverage gets inflated.
"""
import random

import cocotb
from cocotb.triggers import Timer

from riscv_isa import (B_TYPE, I_TYPE, R_TYPE, S_TYPE, SHIFT_IMM, U_TYPE,
                       encode)

# cpu_pkg encodings
ALU_ADD, ALU_SUB, ALU_AND, ALU_OR, ALU_XOR = 0, 1, 2, 3, 4
ALU_SLL, ALU_SRL, ALU_SRA, ALU_SLT, ALU_SLTU, ALU_PASS_B = 5, 6, 7, 8, 9, 10
IMM_I, IMM_S, IMM_B, IMM_U, IMM_J, IMM_NONE = 0, 1, 2, 3, 4, 7

ALU_BY_MNEMONIC = {
    "add": ALU_ADD, "sub": ALU_SUB, "sll": ALU_SLL, "slt": ALU_SLT,
    "sltu": ALU_SLTU, "xor": ALU_XOR, "srl": ALU_SRL, "sra": ALU_SRA,
    "or": ALU_OR, "and": ALU_AND,
    "addi": ALU_ADD, "slti": ALU_SLT, "sltiu": ALU_SLTU, "xori": ALU_XOR,
    "ori": ALU_OR, "andi": ALU_AND,
    "slli": ALU_SLL, "srli": ALU_SRL, "srai": ALU_SRA,
}

M_MNEMONICS = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]
MD_OP = {name: index for index, name in enumerate(M_MNEMONICS)}

BASE = {
    "reg_write": 0, "mem_write": 0, "mem_to_reg": 0, "alu_src_a_pc": 0,
    "alu_src_b_imm": 0, "use_mul_div": 0, "is_branch": 0, "is_jal": 0,
    "is_jalr": 0, "link_pc": 0, "illegal": 0,
}


def expected_controls(mnemonic: str) -> dict:
    """Decode contract of spec.md (FR-03/FR-04/FR-08), restated here."""
    exp = dict(BASE)
    if mnemonic == "lui":
        exp.update(reg_write=1, alu_src_b_imm=1, imm_format=IMM_U,
                   alu_op=ALU_PASS_B)
    elif mnemonic == "auipc":
        exp.update(reg_write=1, alu_src_a_pc=1, alu_src_b_imm=1,
                   imm_format=IMM_U, alu_op=ALU_ADD)
    elif mnemonic == "jal":
        exp.update(reg_write=1, alu_src_a_pc=1, alu_src_b_imm=1, is_jal=1,
                   link_pc=1, imm_format=IMM_J, alu_op=ALU_ADD)
    elif mnemonic == "jalr":
        exp.update(reg_write=1, alu_src_b_imm=1, is_jalr=1, link_pc=1,
                   imm_format=IMM_I, alu_op=ALU_ADD)
    elif mnemonic in B_TYPE:
        exp.update(is_branch=1, alu_src_a_pc=1, alu_src_b_imm=1,
                   imm_format=IMM_B, alu_op=ALU_ADD)
    elif mnemonic in ("lb", "lh", "lw", "lbu", "lhu"):
        exp.update(reg_write=1, mem_to_reg=1, alu_src_b_imm=1,
                   imm_format=IMM_I, alu_op=ALU_ADD)
    elif mnemonic in S_TYPE:
        exp.update(mem_write=1, alu_src_b_imm=1, imm_format=IMM_S,
                   alu_op=ALU_ADD)
    elif mnemonic in SHIFT_IMM or mnemonic in ("addi", "slti", "sltiu",
                                               "xori", "ori", "andi"):
        exp.update(reg_write=1, alu_src_b_imm=1, imm_format=IMM_I,
                   alu_op=ALU_BY_MNEMONIC[mnemonic])
    elif mnemonic in M_MNEMONICS:
        exp.update(reg_write=1, use_mul_div=1, imm_format=IMM_NONE,
                   md_op=MD_OP[mnemonic])
    elif mnemonic in R_TYPE:
        exp.update(reg_write=1, imm_format=IMM_NONE,
                   alu_op=ALU_BY_MNEMONIC[mnemonic])
    else:
        raise AssertionError(f"no contract for {mnemonic}")
    return exp


async def apply_word(dut, word: int) -> None:
    dut.instr.value = word
    await Timer(1, unit="ns")


async def check_instruction(dut, mnemonic: str, word: int) -> None:
    await apply_word(dut, word)
    exp = expected_controls(mnemonic)
    for signal, want in exp.items():
        got = int(getattr(dut, signal).value)
        assert got == want, (
            f"FR-03/FR-04 violated: {mnemonic} (0x{word:08x}) -> "
            f"{signal} = {got}, expected {want}"
        )


@cocotb.test()
async def test_all_declared_instructions(dut):
    """All 45 declared instructions decode to the contracted control word."""
    random.seed(20260904)
    mnemonics = (list(R_TYPE) + list(I_TYPE) + list(SHIFT_IMM) + list(S_TYPE)
                 + list(B_TYPE) + list(U_TYPE) + ["jal"])
    assert len(mnemonics) == 45, f"expected 45 declared instructions, got {len(mnemonics)}"

    for mnemonic in mnemonics:
        for _ in range(8):  # random register fields and immediates
            word = encode(
                mnemonic,
                rd=random.randrange(32), rs1=random.randrange(32),
                rs2=random.randrange(32),
                imm=random.randrange(-2048, 2048) & 0xFFFFF000
                if mnemonic in U_TYPE else random.randrange(-2048, 2048),
            )
            await check_instruction(dut, mnemonic, word)


@cocotb.test()
async def test_out_of_scope_instructions_are_illegal(dut):
    """# REQ: FR-14 -- fence/ecall/ebreak/CSR are not implemented."""
    cases = {
        "fence":  0x0FF0000F,
        "fence.i": 0x0000100F,
        "ecall":  0x00000073,
        "ebreak": 0x00100073,
        "csrrw":  0x30001073,
        "csrrs":  0x00002073,
        "system_zero": 0x00000000,
        "all_ones": 0xFFFFFFFF,
    }
    for name, word in cases.items():
        await apply_word(dut, word)
        assert int(dut.illegal.value) == 1, (
            f"FR-14 violated: {name} (0x{word:08x}) not flagged illegal"
        )
        assert int(dut.reg_write.value) == 0, (
            f"FR-14 violated: {name} writes a register"
        )
        assert int(dut.mem_write.value) == 0, (
            f"FR-14 violated: {name} writes memory"
        )


@cocotb.test()
async def test_reserved_encodings_are_illegal(dut):
    """# REQ: FR-14 -- reserved funct3/funct7 must not alias a real op."""
    cases = {
        # OP with an undefined funct7
        "op_funct7_0x20_sll": (0b0100000 << 25) | (0b001 << 12) | 0b0110011,
        "op_funct7_0x02":     (0b0000010 << 25) | 0b0110011,
        # shift-immediate with a non-zero upper field
        "slli_bad_funct7":    (0b0100000 << 25) | (0b001 << 12) | 0b0010011,
        "srli_bad_funct7":    (0b0010000 << 25) | (0b101 << 12) | 0b0010011,
        # RV64-only widths
        "ld":                 (0b011 << 12) | 0b0000011,
        "lwu":                (0b110 << 12) | 0b0000011,
        "sd":                 (0b011 << 12) | 0b0100011,
        # reserved branch funct3
        "branch_f3_010":      (0b010 << 12) | 0b1100011,
        "branch_f3_011":      (0b011 << 12) | 0b1100011,
        # jalr with a non-zero funct3
        "jalr_f3_001":        (0b001 << 12) | 0b1100111,
    }
    for name, word in cases.items():
        await apply_word(dut, word)
        assert int(dut.illegal.value) == 1, (
            f"FR-14 violated: {name} (0x{word:08x}) not flagged illegal"
        )
        assert int(dut.reg_write.value) == 0, (
            f"FR-14 violated: {name} writes a register"
        )
        assert int(dut.mem_write.value) == 0, (
            f"FR-14 violated: {name} writes memory"
        )


@cocotb.test()
async def test_m_extension_md_op_is_funct3(dut):
    """# REQ: FR-04 -- md_op forwards funct3 verbatim for funct7 = 0000001."""
    for mnemonic in M_MNEMONICS:
        word = encode(mnemonic, rd=5, rs1=6, rs2=7)
        await apply_word(dut, word)
        got = int(dut.md_op.value)
        want = MD_OP[mnemonic]
        assert got == want, (
            f"FR-04 violated: {mnemonic} md_op = {got:03b}, expected {want:03b}"
        )
        assert int(dut.use_mul_div.value) == 1, (
            f"FR-04 violated: {mnemonic} did not select the mul/div unit"
        )
