#!/usr/bin/env python3
"""Extensão RV32M — família de divisão: DIV, DIVU, REM, REMU.

REQ: FR-RV-12 (extensão RV32IM), FR-RV-13 (as instruções), FR-RV-14 (casos
especiais da especificação RISC-V), FR-RV-22 (zero, negativos, maior e menor
valor representável, divisão por zero, overflow da divisão),
FR-RV-23 (modelo de referência), FR-RV-24 (métricas).

A especificação RISC-V não privilegiada é explícita: **não há trap** em divisão
por zero nem em overflow da divisão com sinal. As duas produzem valor definido,
e o processador continua executando. Isso é verificado aqui de duas formas: o
valor tem de bater com o modelo de referência, e o programa tem de alcançar o
auto-laço de parada (se travasse, o harness levantaria CpuTimeout).

Rodar:
  pytest examples/RISCV32I/test/test_rv32m_div.py -v
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

DIV_OPS = ["div", "divu", "rem", "remu"]

INT32_MIN = 0x80000000
INT32_MAX = 0x7FFFFFFF


def _sweep(tmp_path, mnemonic: str, name: str, pairs, reqs: list[str]):
    return run_program(
        tmp_path, name,
        build_program(mnemonic, pairs),
        expect_ram=expected_ram(mnemonic, pairs),
        max_cycles=20000,
        rv32m=True,
        requirements=reqs,
    )


def _table(tmp_path, name: str, mnemonic: str,
           cases: list[tuple[int, int]], reqs: list[str]):
    """Roda uma lista de pares e confere cada slot contra o modelo."""
    return run_program(
        tmp_path, name,
        build_program(mnemonic, cases),
        expect_ram=expected_ram(mnemonic, cases),
        max_cycles=3000, rv32m=True, requirements=reqs,
    )


# --------------------------------------------------------------------------
# Varredura completa
# --------------------------------------------------------------------------

class TestDiv:
    """DIV: divisão com sinal, truncada para zero."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("div"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "div", name, pairs, ["FR-RV-13", "FR-RV-22"])


class TestDivu:
    """DIVU: divisão sem sinal."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("divu"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "divu", name, pairs, ["FR-RV-13", "FR-RV-22"])


class TestRem:
    """REM: resto com sinal, com o sinal do DIVIDENDO."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("rem"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "rem", name, pairs, ["FR-RV-13", "FR-RV-22"])


class TestRemu:
    """REMU: resto sem sinal."""

    @pytest.mark.parametrize("name,pairs", sweep_cases("remu"))
    def test_sweep(self, tmp_path, name, pairs):
        _sweep(tmp_path, "remu", name, pairs, ["FR-RV-13", "FR-RV-22"])


# --------------------------------------------------------------------------
# Casos especiais da especificação RISC-V (FR-RV-14)
# --------------------------------------------------------------------------

class TestDivisionByZero:
    """Divisão por zero: valor definido, sem trap, sem travar (FR-RV-14)."""

    @pytest.mark.parametrize("mnemonic", DIV_OPS)
    def test_divide_by_zero_produces_the_specified_value(self, tmp_path, mnemonic):
        dividends = [0, 1, 0xFFFFFFFF, INT32_MAX, INT32_MIN, 0x12345678]
        cases = [(d, 0) for d in dividends]
        run = _table(tmp_path, f"{mnemonic}_by_zero", mnemonic, cases,
                     ["FR-RV-14", "FR-RV-22"])
        # o programa CHEGOU ao auto-laço: não houve trap nem travamento
        assert run.metrics["halted"] is True, \
            f"{mnemonic} por zero deveria continuar a execução (FR-RV-14)"

    def test_the_four_specified_values(self, tmp_path):
        """Confere literalmente a tabela da spec, num único programa.

            DIV  x, 0 -> -1          DIVU x, 0 -> 2^32-1
            REM  x, 0 -> x           REMU x, 0 -> x
        """
        x = 0x12345678
        assert ref.div(x, 0) == 0xFFFFFFFF
        assert ref.divu(x, 0) == 0xFFFFFFFF
        assert ref.rem(x, 0) == x
        assert ref.remu(x, 0) == x

        asm = f"""
        # REQ: FR-RV-14 -- divisao por zero nao gera trap em RISC-V
            li   x18, {RAM_BASE}
            li   x10, {sig(x)}
            li   x11, 0
            div  x12, x10, x11
            sw   x12, 0(x18)
            divu x13, x10, x11
            sw   x13, 4(x18)
            rem  x14, x10, x11
            sw   x14, 8(x18)
            remu x15, x10, x11
            sw   x15, 12(x18)
            # a execucao continua normalmente depois das quatro
            addi x16, x0, 1234
            sw   x16, 16(x18)
        {HALT}
        """
        run_program(
            tmp_path, "div_zero_table", asm,
            expect_ram={result_addr(0): ref.div(x, 0),
                        result_addr(1): ref.divu(x, 0),
                        result_addr(2): ref.rem(x, 0),
                        result_addr(3): ref.remu(x, 0),
                        result_addr(4): 1234},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-14"],
        )


class TestSignedOverflow:
    def test_int32_min_divided_by_minus_one(self, tmp_path):
        """Overflow da divisão com sinal (FR-RV-14).

            (-2^31) / (-1) -> -2^31   (o resultado matemático não é
                                       representável; a spec manda envolver)
            (-2^31) % (-1) -> 0
        DIVU e REMU sobre os MESMOS bits não são overflow, porque
        0x80000000 / 0xFFFFFFFF sem sinal é 0, resto 0x80000000.
        """
        assert ref.div(INT32_MIN, 0xFFFFFFFF) == INT32_MIN
        assert ref.rem(INT32_MIN, 0xFFFFFFFF) == 0

        asm = f"""
        # REQ: FR-RV-14 -- overflow da divisao com sinal
            li   x18, {RAM_BASE}
            li   x10, {sig(INT32_MIN)}
            li   x11, -1
            div  x12, x10, x11
            sw   x12, 0(x18)
            rem  x13, x10, x11
            sw   x13, 4(x18)
            divu x14, x10, x11
            sw   x14, 8(x18)
            remu x15, x10, x11
            sw   x15, 12(x18)
        {HALT}
        """
        run_program(
            tmp_path, "div_overflow", asm,
            expect_ram={result_addr(0): ref.div(INT32_MIN, 0xFFFFFFFF),
                        result_addr(1): ref.rem(INT32_MIN, 0xFFFFFFFF),
                        result_addr(2): ref.divu(INT32_MIN, 0xFFFFFFFF),
                        result_addr(3): ref.remu(INT32_MIN, 0xFFFFFFFF)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-14", "FR-RV-22"],
        )


class TestRoundingAndSign:
    def test_div_truncates_toward_zero_and_rem_follows_the_dividend(self, tmp_path):
        """A regra de arredondamento e a regra de sinal do resto (FR-RV-14).

        RISC-V trunca em direção a ZERO, não para -infinito. Portanto
        (-7)/2 = -3 e não -4. E o resto acompanha o sinal do DIVIDENDO:
        (-7)%2 = -1, mas 7%(-2) = +1.
        Este teste falha se a implementação tivesse usado a divisão
        euclidiana ou o sinal do divisor.
        """
        cases = [(-7, 2), (7, -2), (-7, -2), (7, 2),
                 (-1, 2), (1, -2), (-9, 4), (9, -4)]
        pairs = [(a & 0xFFFFFFFF, b & 0xFFFFFFFF) for a, b in cases]

        # sanidade do próprio modelo antes de cobrar do hardware
        assert ref.to_signed32(ref.div(pairs[0][0], pairs[0][1])) == -3
        assert ref.to_signed32(ref.rem(pairs[0][0], pairs[0][1])) == -1
        assert ref.to_signed32(ref.rem(pairs[1][0], pairs[1][1])) == 1

        _table(tmp_path, "div_trunc", "div", pairs, ["FR-RV-14", "FR-RV-22"])
        _table(tmp_path, "rem_sign", "rem", pairs, ["FR-RV-14", "FR-RV-22"])

    def test_divisor_larger_than_dividend(self, tmp_path):
        """Quociente zero e resto igual ao dividendo."""
        cases = [(3, 10), (0xFFFFFFFD, 10), (1, INT32_MAX), (5, 0x80000000)]
        for op in DIV_OPS:
            _table(tmp_path, f"{op}_small", op, cases,
                   ["FR-RV-13", "FR-RV-22"])


class TestExtremes:
    def test_largest_and_smallest_representable(self, tmp_path):
        """Maior e menor valor representável em todas as combinações."""
        vals = [INT32_MIN, INT32_MAX, 0xFFFFFFFF, 1, 0]
        cases = [(a, b) for a in vals for b in vals]
        for op in DIV_OPS:
            _table(tmp_path, f"{op}_extremes", op, cases,
                   ["FR-RV-14", "FR-RV-22"])


class TestOperandAliasing:
    @pytest.mark.parametrize("mnemonic", DIV_OPS)
    def test_rd_equals_an_operand(self, tmp_path, mnemonic):
        a, b = 0xDEADBEEF, 0x00001234
        asm = f"""
        # REQ: FR-RV-13 -- rd = rs1, rd = rs2, rd = rs1 = rs2
            li   x18, {RAM_BASE}
            li   x10, {sig(a)}
            li   x11, {sig(b)}
            {mnemonic} x10, x10, x11
            sw   x10, 0(x18)
            li   x10, {sig(a)}
            li   x11, {sig(b)}
            {mnemonic} x11, x10, x11
            sw   x11, 4(x18)
            li   x10, {sig(a)}
            {mnemonic} x10, x10, x10
            sw   x10, 8(x18)
        {HALT}
        """
        run_program(
            tmp_path, f"{mnemonic}_alias", asm,
            expect_ram={result_addr(0): ref.apply_m(mnemonic, a, b),
                        result_addr(1): ref.apply_m(mnemonic, a, b),
                        result_addr(2): ref.apply_m(mnemonic, a, a)},
            max_cycles=500, rv32m=True, requirements=["FR-RV-13"],
        )


class TestX0:
    @pytest.mark.parametrize("mnemonic", DIV_OPS)
    def test_x0_destination_and_operands(self, tmp_path, mnemonic):
        """FR-RV-04: x0 é sempre zero, na leitura e na escrita."""
        v = 0x0000ABCD
        asm = f"""
        # REQ: FR-RV-04, FR-RV-13
            li   x18, {RAM_BASE}
            li   x10, {sig(v)}
            {mnemonic} x0, x10, x10         # escrita descartada
            sw   x0, 0(x18)
            {mnemonic} x12, x10, x0         # divisao por zero via x0
            sw   x12, 4(x18)
            {mnemonic} x13, x0, x10         # dividendo zero
            sw   x13, 8(x18)
        {HALT}
        """
        run_program(
            tmp_path, f"{mnemonic}_x0", asm,
            expect_regs={0: 0},
            expect_ram={result_addr(0): 0,
                        result_addr(1): ref.apply_m(mnemonic, v, 0),
                        result_addr(2): ref.apply_m(mnemonic, 0, v)},
            max_cycles=500, rv32m=True,
            requirements=["FR-RV-04", "FR-RV-13", "FR-RV-14"],
        )
