#!/usr/bin/env python3
"""Validação do montador RV32I/RV32IM e do modelo de referência.

REQ: FR-RV-19, FR-RV-20, FR-RV-23, FR-RV-14

Estes testes existem por causa do risco declarado em `specs/decisions.md`,
ADR-004: o montador é código novo do projeto, e um bug nele apareceria como
falha de hardware. Portanto ele é conferido contra encodings da especificação
RISC-V não privilegiada ANTES de ser usado para gerar imagens de teste.

Os valores esperados de encoding abaixo foram derivados manualmente dos
formatos R/I/S/B/U/J da especificação, campo por campo.

Rodar:  pytest examples/RISCV32I/test/test_toolchain.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_model as ref  # noqa: E402
from rv_assembler import (  # noqa: E402
    AssemblyError,
    assemble,
    parse_register,
    read_ram_image,
    write_ram_image,
)


def asm1(text: str, **kw) -> int:
    """Monta uma única instrução e devolve a palavra."""
    words = assemble(text, **kw)
    assert len(words) == 1, f"esperava 1 palavra, obteve {len(words)}: {words}"
    return words[0]


# ==========================================================================
# Registradores
# ==========================================================================

class TestRegisters:
    def test_numeric_names(self):
        for i in range(32):
            assert parse_register(f"x{i}") == i

    @pytest.mark.parametrize("name,idx", [
        ("zero", 0), ("ra", 1), ("sp", 2), ("gp", 3), ("tp", 4),
        ("t0", 5), ("t1", 6), ("t2", 7), ("s0", 8), ("fp", 8), ("s1", 9),
        ("a0", 10), ("a7", 17), ("s2", 18), ("s11", 27),
        ("t3", 28), ("t6", 31),
    ])
    def test_abi_names(self, name, idx):
        assert parse_register(name) == idx

    def test_out_of_range_rejected(self):
        with pytest.raises(AssemblyError):
            parse_register("x32")

    def test_garbage_rejected(self):
        with pytest.raises(AssemblyError):
            parse_register("banana")


# ==========================================================================
# RV32I — encodings conferidos campo por campo
# ==========================================================================

class TestRV32IEncoding:
    def test_nop_is_addi_x0_x0_0(self):
        # A CPU alvo define INSTR_NOP = 0x00000013 em cpu_package.vhd
        assert asm1("nop") == 0x00000013
        assert asm1("addi x0, x0, 0") == 0x00000013

    @pytest.mark.parametrize("src,expected", [
        # R-type: funct7 | rs2 | rs1 | funct3 | rd | opcode(0110011)
        ("add x1, x2, x3", 0x003100B3),
        ("sub x1, x2, x3", 0x403100B3),
        ("sll x1, x2, x3", 0x003110B3),
        ("slt x1, x2, x3", 0x003120B3),
        ("sltu x1, x2, x3", 0x003130B3),
        ("xor x1, x2, x3", 0x003140B3),
        ("srl x1, x2, x3", 0x003150B3),
        ("sra x1, x2, x3", 0x403150B3),
        ("or x1, x2, x3", 0x003160B3),
        ("and x1, x2, x3", 0x003170B3),
    ])
    def test_r_type(self, src, expected):
        assert asm1(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("addi x1, x2, 1", 0x00110093),
        ("addi x1, x2, -1", 0xFFF10093),
        ("addi x1, x2, 2047", 0x7FF10093),
        ("addi x1, x2, -2048", 0x80010093),
        ("slti x1, x2, 5", 0x00512093),
        ("sltiu x1, x2, 5", 0x00513093),
        ("xori x1, x2, 5", 0x00514093),
        ("ori x1, x2, 5", 0x00516093),
        ("andi x1, x2, 5", 0x00517093),
    ])
    def test_i_type_arith(self, src, expected):
        assert asm1(src) == expected

    def test_i_type_immediate_range_enforced(self):
        with pytest.raises(AssemblyError, match="12 bits"):
            asm1("addi x1, x2, 2048")
        with pytest.raises(AssemblyError, match="12 bits"):
            asm1("addi x1, x2, -2049")

    @pytest.mark.parametrize("src,expected", [
        ("slli x1, x2, 1", 0x00111093),
        ("slli x1, x2, 31", 0x01F11093),
        ("srli x1, x2, 1", 0x00115093),
        ("srai x1, x2, 1", 0x40115093),
        ("srai x1, x2, 31", 0x41F15093),
    ])
    def test_shift_immediates(self, src, expected):
        assert asm1(src) == expected

    def test_shamt_range_enforced(self):
        with pytest.raises(AssemblyError, match="5 bits"):
            asm1("slli x1, x2, 32")

    @pytest.mark.parametrize("src,expected", [
        ("lb x1, 0(x2)", 0x00010083),
        ("lh x1, 0(x2)", 0x00011083),
        ("lw x1, 0(x2)", 0x00012083),
        ("lbu x1, 0(x2)", 0x00014083),
        ("lhu x1, 0(x2)", 0x00015083),
        ("lw x1, 4(x2)", 0x00412083),
        ("lw x1, -4(x2)", 0xFFC12083),
        ("lw x1, (x2)", 0x00012083),
    ])
    def test_loads(self, src, expected):
        assert asm1(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("sb x1, 0(x2)", 0x00110023),
        ("sh x1, 0(x2)", 0x00111023),
        ("sw x1, 0(x2)", 0x00112023),
        ("sw x1, 4(x2)", 0x00112223),
        ("sw x1, -4(x2)", 0xFE112E23),
    ])
    def test_stores(self, src, expected):
        assert asm1(src) == expected

    @pytest.mark.parametrize("src,expected", [
        ("lui x1, 1", 0x000010B7),
        ("lui x1, 0xFFFFF", 0xFFFFF0B7),
        ("auipc x1, 1", 0x00001097),
    ])
    def test_u_type(self, src, expected):
        assert asm1(src) == expected

    def test_branch_backward_self_loop(self):
        # `here: beq x0, x0, here` -> deslocamento 0
        words = assemble("here: beq x0, x0, here")
        assert words[0] == 0x00000063

    def test_jal_self_loop_is_halt_encoding(self):
        # convenção de parada do ADR-003: j para si mesmo = 0x0000006f
        words = assemble("halt: j halt")
        assert words[0] == 0x0000006F

    def test_branch_forward_offset(self):
        # beq x1,x2,+8  => imm=8
        src = """
            beq x1, x2, target
            nop
        target:
            nop
        """
        words = assemble(src)
        assert words[0] == 0x00208463, f"got {words[0]:#010x}"

    def test_branch_offset_range_enforced(self):
        src = "beq x1, x2, far\n" + "nop\n" * 4096 + "far: nop\n"
        with pytest.raises(AssemblyError, match="13 bits"):
            assemble(src)

    @pytest.mark.parametrize("src,expected", [
        ("jalr x1, 0(x2)", 0x000100E7),
        ("jalr x2", 0x000100E7),
        ("ret", 0x00008067),
        ("jr x1", 0x00008067),
    ])
    def test_jalr_forms(self, src, expected):
        assert asm1(src) == expected


# ==========================================================================
# RV32M — encodings (funct7 = 0000001)
# ==========================================================================

class TestRV32MEncoding:
    @pytest.mark.parametrize("src,expected", [
        ("mul x1, x2, x3", 0x023100B3),
        ("mulh x1, x2, x3", 0x023110B3),
        ("mulhsu x1, x2, x3", 0x023120B3),
        ("mulhu x1, x2, x3", 0x023130B3),
        ("div x1, x2, x3", 0x023140B3),
        ("divu x1, x2, x3", 0x023150B3),
        ("rem x1, x2, x3", 0x023160B3),
        ("remu x1, x2, x3", 0x023170B3),
    ])
    def test_m_encodings(self, src, expected):
        assert asm1(src) == expected

    @pytest.mark.parametrize("mnemonic", list(
        ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]))
    def test_funct7_is_one_and_opcode_is_op(self, mnemonic):
        w = asm1(f"{mnemonic} x5, x6, x7")
        assert (w & 0x7F) == 0b0110011, "opcode deve ser OP (0110011)"
        assert ((w >> 25) & 0x7F) == 0b0000001, "funct7 deve ser 0000001"

    def test_m_rejected_when_baseline_only(self):
        """Garante que programas de baseline não usem RV32M (FR-RV-19)."""
        with pytest.raises(AssemblyError, match="RV32M"):
            asm1("mul x1, x2, x3", allow_m=False)

    def test_rv32i_still_assembles_with_m_disabled(self):
        assert asm1("add x1, x2, x3", allow_m=False) == 0x003100B3


# ==========================================================================
# Instruções fora do escopo / não implementadas pela CPU
# ==========================================================================

class TestScopeGuards:
    @pytest.mark.parametrize("mnemonic", ["fence", "ecall", "ebreak"])
    def test_unsupported_rejected_by_default(self, mnemonic):
        """ADR-000: a CPU alvo não implementa FENCE/ECALL/EBREAK."""
        with pytest.raises(AssemblyError, match="não é implementada"):
            asm1(mnemonic)

    def test_unknown_instruction_rejected(self):
        with pytest.raises(AssemblyError, match="desconhecida"):
            asm1("frobnicate x1, x2, x3")

    def test_mips_style_instruction_rejected(self):
        """FR-RV-03: ISA estritamente RISC-V, nada de MIPS."""
        for mips in ["addu x1, x2, x3", "lw x1, x2, x3", "syscall", "multu x1, x2"]:
            with pytest.raises(AssemblyError):
                assemble(mips)


# ==========================================================================
# Pseudo-instruções e labels
# ==========================================================================

class TestPseudoInstructions:
    def test_mv(self):
        assert asm1("mv x1, x2") == asm1("addi x1, x2, 0")

    def test_not(self):
        assert asm1("not x1, x2") == asm1("xori x1, x2, -1")

    def test_neg(self):
        assert asm1("neg x1, x2") == asm1("sub x1, x0, x2")

    def test_li_small_is_one_instruction(self):
        assert assemble("li x1, 5") == [asm1("addi x1, x0, 5")]

    def test_li_negative_small(self):
        assert assemble("li x1, -5") == [asm1("addi x1, x0, -5")]

    def test_li_large_is_lui_plus_addi(self):
        words = assemble("li x1, 0x12345678")
        assert len(words) == 2
        # reconstruir o valor: lui carrega hi<<12, addi soma lo com sinal
        hi = (words[0] >> 12) & 0xFFFFF
        lo = (words[1] >> 20) & 0xFFF
        lo_signed = lo - 0x1000 if lo & 0x800 else lo
        assert ((hi << 12) + lo_signed) & 0xFFFFFFFF == 0x12345678

    @pytest.mark.parametrize("value", [
        0x00000000, 0x000007FF, 0x00000800, 0x7FFFFFFF,
        0x80000000, 0xFFFFFFFF, 0xDEADBEEF, 0x00001000, 0xFFFFF800,
    ])
    def test_li_roundtrip_all_magnitudes(self, value):
        """`li` deve produzir exatamente o valor pedido, em 1 ou 2 instruções."""
        words = assemble(f"li x1, {value if value < 0x80000000 else value - (1 << 32)}")
        acc = 0
        for w in words:
            if (w & 0x7F) == 0b0110111:            # lui
                acc = ((w >> 12) & 0xFFFFF) << 12
            else:                                   # addi
                imm = (w >> 20) & 0xFFF
                acc += imm - 0x1000 if imm & 0x800 else imm
        assert acc & 0xFFFFFFFF == value

    def test_branch_pseudo_beqz(self):
        assert assemble("a: beqz x5, a") == assemble("a: beq x5, x0, a")

    def test_branch_pseudo_bgt_swaps_operands(self):
        assert assemble("a: bgt x5, x6, a") == assemble("a: blt x6, x5, a")

    def test_duplicate_label_rejected(self):
        with pytest.raises(AssemblyError, match="duplicado"):
            assemble("a: nop\na: nop")

    def test_undefined_label_rejected(self):
        with pytest.raises(AssemblyError, match="não definido"):
            assemble("beq x0, x0, nowhere")

    def test_multiple_labels_same_line(self):
        words = assemble("a: b: nop")
        assert len(words) == 1

    def test_comment_styles(self):
        src = """
        # hash
        nop     // slashes
        nop     ; semicolon
        """
        assert assemble(src) == [0x13, 0x13]


# ==========================================================================
# Imagem .ram  (formato do ADR-003)
# ==========================================================================

class TestRamImage:
    def test_format_is_one_hex_word_per_line(self, tmp_path):
        p = write_ram_image([0x00000013, 0xDEADBEEF], tmp_path / "t.ram")
        lines = p.read_text().strip().splitlines()
        assert lines == ["00000013", "deadbeef"]

    def test_roundtrip(self, tmp_path):
        """TR1.3: montar, gravar, reler e obter as mesmas palavras."""
        words = assemble("""
            li x1, 100
            li x2, 7
            add x3, x1, x2
        halt:
            j halt
        """)
        p = write_ram_image(words, tmp_path / "rt.ram")
        assert read_ram_image(p) == words

    def test_header_comments_are_ignored_on_read(self, tmp_path):
        p = write_ram_image([0x13], tmp_path / "h.ram", header="programa de teste\nlinha 2")
        text = p.read_text()
        assert text.startswith("# programa de teste")
        assert read_ram_image(p) == [0x13]

    def test_blank_and_comment_lines_ignored(self, tmp_path):
        p = tmp_path / "c.ram"
        p.write_text("# c\n\n00000013\n\n# outro\ndeadbeef\n")
        assert read_ram_image(p) == [0x13, 0xDEADBEEF]

    def test_invalid_line_rejected(self, tmp_path):
        p = tmp_path / "bad.ram"
        p.write_text("00000013\nnot_hex\n")
        with pytest.raises(AssemblyError, match="inválida"):
            read_ram_image(p)

    def test_index_zero_maps_to_address_zero(self, tmp_path):
        """ADR-003: linha n corresponde ao endereço de byte 4*n."""
        words = [0x11111111, 0x22222222, 0x33333333]
        p = write_ram_image(words, tmp_path / "a.ram")
        back = read_ram_image(p)
        for n, w in enumerate(back):
            assert w == words[n], f"endereço {4 * n:#x} divergiu"


# ==========================================================================
# Modelo de referência — extensão M (FR-RV-14)
# ==========================================================================

class TestReferenceModelM:
    def test_mul_basic(self):
        assert ref.mul(6, 7) == 42

    def test_mul_is_modular(self):
        assert ref.mul(0x10000, 0x10000) == 0          # 2^32 mod 2^32
        assert ref.mul(0xFFFFFFFF, 0xFFFFFFFF) == 1    # (-1)*(-1)

    def test_mulh_signed(self):
        assert ref.mulh(0xFFFFFFFF, 0xFFFFFFFF) == 0   # (-1)*(-1)=1 -> hi=0
        assert ref.mulh(0x7FFFFFFF, 0x7FFFFFFF) == 0x3FFFFFFF

    def test_mulhu_unsigned(self):
        assert ref.mulhu(0xFFFFFFFF, 0xFFFFFFFF) == 0xFFFFFFFE

    def test_mulhsu_mixed(self):
        # -1 (signed) * 0xFFFFFFFF (unsigned 4294967295) = -4294967295
        # -4294967295 >> 32 = -1 -> 0xFFFFFFFF
        assert ref.mulhsu(0xFFFFFFFF, 0xFFFFFFFF) == 0xFFFFFFFF

    def test_mulh_variants_differ(self):
        """Se as três variantes 'high' coincidirem, o teste não discrimina.

        Para separar as três é preciso rs1 negativo E rs2 com o bit 31 ligado,
        de modo que a interpretação de rs2 (signed vs unsigned) importe.
        rs1 = -1, rs2 = 0x80000000:
          mulh   = (-1 * -2^31) >> 32           = 0
          mulhu  = (2^32-1) * 2^31 >> 32        = 0x7FFFFFFF
          mulhsu = (-1 * 2^31) >> 32            = 0xFFFFFFFF
        """
        a, b = 0xFFFFFFFF, 0x80000000
        assert ref.mulh(a, b) == 0x00000000
        assert ref.mulhu(a, b) == 0x7FFFFFFF
        assert ref.mulhsu(a, b) == 0xFFFFFFFF
        assert len({ref.mulh(a, b), ref.mulhu(a, b), ref.mulhsu(a, b)}) == 3

    def test_mulh_equals_mulhsu_when_rs2_positive(self):
        """Propriedade: com rs2 positivo, signed e unsigned coincidem em rs2."""
        for a in ref.EDGE_VALUES:
            for b in [0x00000000, 0x00000001, 0x00000002, 0x7FFFFFFF]:
                assert ref.mulh(a, b) == ref.mulhsu(a, b), f"a={a:#x} b={b:#x}"

    # --- divisão: casos normais ---
    def test_div_truncates_toward_zero(self):
        assert ref.div(7, 2) == 3
        assert ref.to_signed32(ref.div(0xFFFFFFF9, 2)) == -3   # -7/2 = -3
        assert ref.to_signed32(ref.div(7, 0xFFFFFFFE)) == -3   # 7/-2 = -3

    def test_rem_sign_follows_dividend(self):
        assert ref.rem(7, 2) == 1
        assert ref.to_signed32(ref.rem(0xFFFFFFF9, 2)) == -1   # -7 % 2 = -1
        assert ref.to_signed32(ref.rem(7, 0xFFFFFFFE)) == 1    # 7 % -2 = 1

    def test_divu_remu(self):
        assert ref.divu(7, 2) == 3
        assert ref.remu(7, 2) == 1
        assert ref.divu(0xFFFFFFFF, 2) == 0x7FFFFFFF

    # --- divisão por zero (spec RISC-V: sem trap) ---
    def test_div_by_zero(self):
        assert ref.div(42, 0) == 0xFFFFFFFF        # -1
        assert ref.div(0, 0) == 0xFFFFFFFF

    def test_divu_by_zero(self):
        assert ref.divu(42, 0) == 0xFFFFFFFF       # 2^32-1
        assert ref.divu(0, 0) == 0xFFFFFFFF

    def test_rem_by_zero_returns_dividend(self):
        assert ref.rem(42, 0) == 42
        assert ref.rem(0x80000000, 0) == 0x80000000

    def test_remu_by_zero_returns_dividend(self):
        assert ref.remu(42, 0) == 42
        assert ref.remu(0xFFFFFFFF, 0) == 0xFFFFFFFF

    # --- overflow de divisão com sinal ---
    def test_div_overflow(self):
        """-2^31 / -1 = -2^31 (sem trap, sem saturação)."""
        assert ref.div(0x80000000, 0xFFFFFFFF) == 0x80000000

    def test_rem_overflow(self):
        """-2^31 % -1 = 0."""
        assert ref.rem(0x80000000, 0xFFFFFFFF) == 0

    def test_divu_no_overflow_case(self):
        # sem sinal, -2^31 é 2147483648 e -1 é 4294967295
        assert ref.divu(0x80000000, 0xFFFFFFFF) == 0
        assert ref.remu(0x80000000, 0xFFFFFFFF) == 0x80000000

    # --- invariante algébrica ---
    @pytest.mark.parametrize("a", ref.EDGE_VALUES)
    @pytest.mark.parametrize("b", ref.EDGE_VALUES)
    def test_div_rem_identity(self, a, b):
        """Para b != 0: a == (a/b)*b + a%b, em aritmética modular de 32 bits."""
        if b == 0:
            pytest.skip("divisor zero tem regra própria")
        q, r = ref.div(a, b), ref.rem(a, b)
        assert (ref.mul(q, b) + r) & ref.MASK32 == (a & ref.MASK32)

    @pytest.mark.parametrize("a", ref.EDGE_VALUES)
    @pytest.mark.parametrize("b", ref.EDGE_VALUES)
    def test_divu_remu_identity(self, a, b):
        if b == 0:
            pytest.skip("divisor zero tem regra própria")
        q, r = ref.divu(a, b), ref.remu(a, b)
        assert (ref.mul(q, b) + r) & ref.MASK32 == (a & ref.MASK32)

    @pytest.mark.parametrize("a", ref.EDGE_VALUES)
    @pytest.mark.parametrize("b", ref.EDGE_VALUES)
    def test_all_results_are_32bit(self, a, b):
        """Nenhuma operação pode vazar acima de 32 bits."""
        for op in ref.M_OPS:
            v = ref.apply_m(op, a, b)
            assert 0 <= v <= 0xFFFFFFFF, f"{op}({a:#x},{b:#x}) = {v:#x}"

    def test_signed_unsigned_conversions(self):
        assert ref.to_signed32(0xFFFFFFFF) == -1
        assert ref.to_signed32(0x80000000) == ref.INT32_MIN
        assert ref.to_signed32(0x7FFFFFFF) == ref.INT32_MAX
        assert ref.to_unsigned32(-1) == 0xFFFFFFFF
