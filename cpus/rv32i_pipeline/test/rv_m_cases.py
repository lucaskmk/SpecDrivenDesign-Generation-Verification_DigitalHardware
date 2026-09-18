#!/usr/bin/env python3
"""Gerador de programas de teste para a extensão RV32M.

REQ: FR-RV-13 (as oito instruções), FR-RV-22 (valores de borda),
FR-RV-23 (comparação contra modelo de referência).

Por que existe: uma varredura completa de `EDGE_VALUES × EDGE_VALUES` dá 169
pares por instrução. Rodar um programa por par significaria 169 execuções de
GHDL por instrução — dezenas de minutos de simulação sem ganho de cobertura.

Este módulo empacota muitos casos num único programa: carrega o par com `li`,
executa a instrução M e publica o resultado num slot de RAM próprio. Um único
`run_program` verifica então dezenas de casos de uma vez.

Limites respeitados (ver `memory_package.vhd`):
  * a RAM de dados tem 512 bytes = 128 palavras, então no máximo 128 slots;
  * o offset imediato de `sw` é de 12 bits com sinal, e 4*127 = 508 cabe;
  * a ROM tem `ROM_SIZE_WORDS` palavras (1024 por padrão em `rv_build.py`) e
    cada caso custa no máximo 6 palavras (dois `li` de 2 palavras + a
    instrução M + o `sw`).
"""

from __future__ import annotations

from rvverify import reference as ref

MASK32 = 0xFFFFFFFF

# Casos por programa. 80 casos = 320 bytes de RAM e ~480 palavras de ROM,
# ambos com folga confortável dentro dos limites acima.
CHUNK = 80

HALT = "halt:\n    j halt\n"


def sig(value: int) -> str:
    """Literal decimal com sinal, que é o que o `li` do montador aceita."""
    v = value & MASK32
    return str(v - (1 << 32) if v & 0x80000000 else v)


def chunks(items: list, size: int = CHUNK) -> list[list]:
    return [items[i:i + size] for i in range(0, len(items), size)]


def all_pairs(values: list[int] | None = None) -> list[tuple[int, int]]:
    """Produto cartesiano dos valores de borda (FR-RV-22)."""
    vals = values if values is not None else ref.EDGE_VALUES
    return [(a, b) for a in vals for b in vals]


def build_program(mnemonic: str, pairs: list[tuple[int, int]]) -> str:
    """Programa que aplica `mnemonic` a cada par e publica o resultado na RAM.

    O ponteiro da área de resultados fica em x18, os operandos em x10/x11 e o
    resultado em x12 — nenhum deles colide com x0.
    """
    from rv_build import RAM_BASE

    lines = [
        f"# REQ: FR-RV-13, FR-RV-22, FR-RV-23 -- varredura de `{mnemonic}`",
        f"    li   x18, {RAM_BASE}",
    ]
    for i, (a, b) in enumerate(pairs):
        lines += [
            f"    # slot {i}: {mnemonic} {sig(a)}, {sig(b)}",
            f"    li   x10, {sig(a)}",
            f"    li   x11, {sig(b)}",
            f"    {mnemonic:<6} x12, x10, x11",
            f"    sw   x12, {4 * i}(x18)",
        ]
    lines.append(HALT)
    return "\n".join(lines)


def expected_ram(mnemonic: str, pairs: list[tuple[int, int]]) -> dict[int, int]:
    """Resultados esperados, calculados pelo MODELO DE REFERÊNCIA (FR-RV-23).

    Nenhum valor esperado é escrito à mão neste projeto: todos saem de
    `rvverify/reference.py`, que implementa a semântica da especificação RISC-V
    não privilegiada, inclusive os casos especiais da divisão.
    """
    from rv_build import result_addr

    return {
        result_addr(i): ref.apply_m(mnemonic, a, b)
        for i, (a, b) in enumerate(pairs)
    }


def sweep_cases(mnemonic: str) -> list[tuple[str, list[tuple[int, int]]]]:
    """Divide a varredura completa de uma instrução em programas executáveis."""
    return [
        (f"{mnemonic}_sweep{n}", part)
        for n, part in enumerate(chunks(all_pairs()))
    ]
