#!/usr/bin/env python3
"""Extensão RV32M — família de multiplicação: MUL, MULH, MULHSU, MULHU.

REQ: FR-RV-12 (extensão RV32IM), FR-RV-13 (as instruções), FR-RV-22 (zero,
negativos, maior e menor valor representável, overflow modular de 32 bits),
FR-RV-23 (comparação contra modelo de referência), FR-RV-24 (métricas).

Todos os valores esperados vêm de `reference_model.py`. Nenhuma constante
hexadecimal é escrita à mão como resultado esperado — se o modelo e o hardware
discordarem, o teste falha e o relatório aponta os dois valores.

Rodar:
  pytest examples/RISCV32I/test/test_rv32m_mul.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import reference_model as ref  # noqa: E402
from rv_build import RAM_BASE, result_addr, run_program  # noqa: E402
from rv_m_cases import (  # noqa: E402
    HALT,
    build_program,
    expected_ram,
    sig,
    sweep_cases,
)

MUL_OPS = ["mul", "mulh", "mulhsu", "mulhu"]


def _sweep(tmp_path, mnemonic: str, name: str, pairs, reqs: list[str]):
    """Executa uma fatia da varredura e confere todos os slots de uma vez."""
    return run_program(
        tmp_path, name,
        build_program(mnemonic, pairs),
        expect_ram=expected_ram(mnemonic, pairs),
        max_cycles=20000,
        rv32m=True,
        requirements=reqs,
    )


# --------------------------------------------------------------------------
# Varredura completa: EDGE_VALUES x EDGE_VALUES para cada instrução
# --------------------------------------------------------------------------

class TestMul:
    """MUL: 32 bits BAIXOS do produto (FR-RV-13)."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("mul"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "mul", name, pairs, ["FR-RV-13", "FR-RV-22"])


class TestMulh:
    """MULH: 32 bits ALTOS do produto com sinal x com sinal."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("mulh"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "mulh", name, pairs, ["FR-RV-13", "FR-RV-22"])


class TestMulhsu:
    """MULHSU: 32 bits altos de com sinal (rs1) x sem sinal (rs2)."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("mulhsu"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "mulhsu", name, pairs, ["FR-RV-13", "FR-RV-22"])


class TestMulhu:
    """MULHU: 32 bits altos de sem sinal x sem sinal."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("mulhu"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "mulhu", name, pairs, ["FR-RV-13", "FR-RV-22"])


# --------------------------------------------------------------------------
# Casos dirigidos, que uma varredura por si só não deixaria evidentes
# --------------------------------------------------------------------------

class TestSignInterpretation:
    def test_four_variants_differ_for_the_same_operands(self, tmp_path):
        """As quatro instruções TÊM de discordar para o mesmo par de operandos.

        Este é o teste que pega troca de sinal na implementação: com
        rs1 = rs2 = -1, os 32 bits baixos são iguais para todas, mas os altos
        distinguem as três variantes:
            MULH   (-1) x (-1) com sinal      -> produto  1, alto = 0
            MULHU  (2^32-1) x (2^32-1)        -> alto = 0xFFFFFFFE
            MULHSU (-1) x (2^32-1) sem sinal  -> alto = 0xFFFFFFFF
        Se a implementação tratasse todas como o mesmo produto, este teste
        falharia; a varredura sozinha poderia passar por coincidência.
        """
        a = b = 0xFFFFFFFF
        assert len({ref.mulh(a, b), ref.mulhu(a, b), ref.mulhsu(a, b)}) == 3, \
            "premissa do teste quebrada: o modelo de referência não distingue as três"

        asm = f"""
        # REQ: FR-RV-13 -- MULH, MULHSU e MULHU devem diferir
            li   x18, {RAM_BASE}
            li   x10, -1
            li   x11, -1
            mul    x12, x10, x11
            sw   x12, 0(x18)
            mulh   x13, x10, x11
            sw   x13, 4(x18)
            mulhsu x14, x10, x11
            sw   x14, 8(x18)
            mulhu  x15, x10, x11
            sw   x15, 12(x18)
        {HALT}
        """
        run_program(
            tmp_path, "mul_variants", asm,
            expect_regs={12: ref.mul(a, b), 13: ref.mulh(a, b),
                         14: ref.mulhsu(a, b), 15: ref.mulhu(a, b)},
            expect_ram={result_addr(0): ref.mul(a, b),
                        result_addr(1): ref.mulh(a, b),
                        result_addr(2): ref.mulhsu(a, b),
                        result_addr(3): ref.mulhu(a, b)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-13", "FR-RV-22"],
        )


class TestModularOverflow:
    def test_low_and_high_words_split_a_64_bit_product(self, tmp_path):
        """MUL entrega os 32 baixos e MULH os 32 altos do MESMO produto.

        REQ: FR-RV-22 (overflow modular de 32 bits). Com operandos cujo produto
        não cabe em 32 bits, a concatenação MULH:MUL tem de reconstruir o
        produto de 64 bits exato.
        """
        cases = [
            (0x7FFFFFFF, 0x7FFFFFFF),      # maior positivo ao quadrado
            (0x80000000, 0x00000002),      # menor negativo x 2
            (0x12345678, 0x9ABCDEF0),
            (0xFFFF, 0x10001),             # 2^32-1, o maior que ainda cabe
        ]
        lines = [f"    li   x18, {RAM_BASE}"]
        expect = {}
        for i, (a, b) in enumerate(cases):
            lines += [
                f"    li   x10, {sig(a)}",
                f"    li   x11, {sig(b)}",
                f"    mul  x12, x10, x11",
                f"    sw   x12, {8 * i}(x18)",
                f"    mulh x13, x10, x11",
                f"    sw   x13, {8 * i + 4}(x18)",
            ]
            expect[result_addr(2 * i)] = ref.mul(a, b)
            expect[result_addr(2 * i + 1)] = ref.mulh(a, b)
        lines.append(HALT)

        run_program(
            tmp_path, "mul_overflow", "\n".join(lines),
            expect_ram=expect, max_cycles=1000, rv32m=True,
            requirements=["FR-RV-13", "FR-RV-22"],
        )

        # o produto de 64 bits reconstruído tem de bater com Python puro
        for i, (a, b) in enumerate(cases):
            lo = expect[result_addr(2 * i)]
            hi = expect[result_addr(2 * i + 1)]
            assert (hi << 32 | lo) == (ref.to_signed32(a) * ref.to_signed32(b)) & ((1 << 64) - 1)


class TestOperandAliasing:
    @pytest.mark.parametrize("mnemonic", MUL_OPS)
    def test_rd_equals_rs1_and_rd_equals_rs2(self, tmp_path, mnemonic):
        """rd pode ser o mesmo registrador de um operando de entrada.

        REQ: FR-RV-13. Pega implementação que escreveria rd antes de terminar
        de ler os operandos.
        """
        a, b = 0xDEADBEEF, 0x12345678
        exp = ref.apply_m(mnemonic, a, b)
        asm = f"""
        # REQ: FR-RV-13 -- rd = rs1 e rd = rs2
            li   x18, {RAM_BASE}
            li   x10, {sig(a)}
            li   x11, {sig(b)}
            {mnemonic} x10, x10, x11        # rd = rs1
            sw   x10, 0(x18)
            li   x10, {sig(a)}
            li   x11, {sig(b)}
            {mnemonic} x11, x10, x11        # rd = rs2
            sw   x11, 4(x18)
            li   x10, {sig(a)}
            {mnemonic} x10, x10, x10        # rd = rs1 = rs2
            sw   x10, 8(x18)
        {HALT}
        """
        run_program(
            tmp_path, f"{mnemonic}_alias", asm,
            expect_ram={result_addr(0): exp,
                        result_addr(1): exp,
                        result_addr(2): ref.apply_m(mnemonic, a, a)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-13"],
        )


class TestX0:
    @pytest.mark.parametrize("mnemonic", MUL_OPS)
    def test_x0_as_destination_is_discarded(self, tmp_path, mnemonic):
        """FR-RV-04: escrever em x0 é descartado; x0 continua zero."""
        asm = f"""
        # REQ: FR-RV-04, FR-RV-13
            li   x18, {RAM_BASE}
            li   x10, {sig(0x7FFFFFFF)}
            li   x11, {sig(0xFFFFFFFF)}
            {mnemonic} x0, x10, x11         # resultado descartado
            sw   x0, 0(x18)
        {HALT}
        """
        run_program(
            tmp_path, f"{mnemonic}_x0_rd", asm,
            expect_regs={0: 0}, expect_ram={result_addr(0): 0},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-04", "FR-RV-13"],
        )

    @pytest.mark.parametrize("mnemonic", MUL_OPS)
    def test_x0_as_operand_reads_zero(self, tmp_path, mnemonic):
        """FR-RV-04: x0 lido como operando vale zero."""
        v = 0xDEADBEEF
        asm = f"""
        # REQ: FR-RV-04, FR-RV-13
            li   x18, {RAM_BASE}
            li   x10, {sig(v)}
            {mnemonic} x12, x10, x0
            sw   x12, 0(x18)
            {mnemonic} x13, x0, x10
            sw   x13, 4(x18)
        {HALT}
        """
        run_program(
            tmp_path, f"{mnemonic}_x0_src", asm,
            expect_ram={result_addr(0): ref.apply_m(mnemonic, v, 0),
                        result_addr(1): ref.apply_m(mnemonic, 0, v)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-04", "FR-RV-13"],
        )
