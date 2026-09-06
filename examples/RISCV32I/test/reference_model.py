#!/usr/bin/env python3
"""Modelo de referência RV32I/RV32M em Python.

REQ: FR-RV-23 (comparar contra modelo de referência, não contra valores
escritos à mão), FR-RV-14 (semântica exata dos casos especiais da extensão M).

Toda a aritmética respeita palavra de 32 bits, complemento de dois e
wraparound modular 2^32. As regras de divisão seguem a especificação RISC-V
não privilegiada, volume I, capítulo "M" — inclusive o fato de que RISC-V
**não** gera trap em divisão por zero nem em overflow de divisão.
"""

from __future__ import annotations

MASK32 = 0xFFFFFFFF
INT32_MIN = -(1 << 31)          # -2147483648
INT32_MAX = (1 << 31) - 1       # 2147483647
UINT32_MAX = MASK32


# --------------------------------------------------------------------------
# Conversões complemento de dois
# --------------------------------------------------------------------------

def to_signed32(value: int) -> int:
    """Interpreta os 32 bits baixos de `value` como inteiro com sinal."""
    v = value & MASK32
    return v - (1 << 32) if v & 0x80000000 else v


def to_unsigned32(value: int) -> int:
    """Interpreta `value` como inteiro de 32 bits sem sinal."""
    return value & MASK32


# --------------------------------------------------------------------------
# Extensão M — as oito instruções (FR-RV-13)
# --------------------------------------------------------------------------

def mul(rs1: int, rs2: int) -> int:
    """MUL: 32 bits baixos do produto. Sinal é irrelevante nos bits baixos."""
    return (to_signed32(rs1) * to_signed32(rs2)) & MASK32


def mulh(rs1: int, rs2: int) -> int:
    """MULH: 32 bits altos de signed x signed."""
    return ((to_signed32(rs1) * to_signed32(rs2)) >> 32) & MASK32


def mulhu(rs1: int, rs2: int) -> int:
    """MULHU: 32 bits altos de unsigned x unsigned."""
    return ((to_unsigned32(rs1) * to_unsigned32(rs2)) >> 32) & MASK32


def mulhsu(rs1: int, rs2: int) -> int:
    """MULHSU: 32 bits altos de signed(rs1) x unsigned(rs2).

    O deslocamento aritmético para a direita em Python já preserva o sinal
    do produto, que é o comportamento exigido.
    """
    return ((to_signed32(rs1) * to_unsigned32(rs2)) >> 32) & MASK32


def div(rs1: int, rs2: int) -> int:
    """DIV: divisão com sinal, truncada para zero.

    Casos especiais da spec RISC-V:
      - divisor zero            -> -1 (todos os bits em 1)
      - overflow (-2^31 / -1)   -> -2^31
    """
    a, b = to_signed32(rs1), to_signed32(rs2)
    if b == 0:
        return MASK32                       # -1
    if a == INT32_MIN and b == -1:
        return INT32_MIN & MASK32           # overflow: retorna o próprio -2^31
    q = abs(a) // abs(b)
    if (a < 0) != (b < 0):
        q = -q
    return q & MASK32


def divu(rs1: int, rs2: int) -> int:
    """DIVU: divisão sem sinal. Divisor zero -> 2^32-1."""
    a, b = to_unsigned32(rs1), to_unsigned32(rs2)
    if b == 0:
        return MASK32
    return (a // b) & MASK32


def rem(rs1: int, rs2: int) -> int:
    """REM: resto com sinal, com o sinal do dividendo.

    Casos especiais da spec RISC-V:
      - divisor zero            -> dividendo
      - overflow (-2^31 % -1)   -> 0
    """
    a, b = to_signed32(rs1), to_signed32(rs2)
    if b == 0:
        return a & MASK32
    if a == INT32_MIN and b == -1:
        return 0
    r = abs(a) % abs(b)
    if a < 0:
        r = -r
    return r & MASK32


def remu(rs1: int, rs2: int) -> int:
    """REMU: resto sem sinal. Divisor zero -> dividendo."""
    a, b = to_unsigned32(rs1), to_unsigned32(rs2)
    if b == 0:
        return a
    return (a % b) & MASK32


M_OPS = {
    "mul": mul, "mulh": mulh, "mulhsu": mulhsu, "mulhu": mulhu,
    "div": div, "divu": divu, "rem": rem, "remu": remu,
}


def apply_m(op: str, rs1: int, rs2: int) -> int:
    """Aplica uma instrução da extensão M pelo nome."""
    try:
        return M_OPS[op.lower()](rs1, rs2)
    except KeyError as e:
        raise ValueError(f"instrução M desconhecida: {op!r}") from e


# --------------------------------------------------------------------------
# Subconjunto RV32I usado pelos testes de baseline
# --------------------------------------------------------------------------

def add(rs1: int, rs2: int) -> int:
    return (to_unsigned32(rs1) + to_unsigned32(rs2)) & MASK32


def sub(rs1: int, rs2: int) -> int:
    return (to_unsigned32(rs1) - to_unsigned32(rs2)) & MASK32


def sll(rs1: int, rs2: int) -> int:
    return (to_unsigned32(rs1) << (rs2 & 0x1F)) & MASK32


def srl(rs1: int, rs2: int) -> int:
    return (to_unsigned32(rs1) >> (rs2 & 0x1F)) & MASK32


def sra(rs1: int, rs2: int) -> int:
    return (to_signed32(rs1) >> (rs2 & 0x1F)) & MASK32


def slt(rs1: int, rs2: int) -> int:
    return 1 if to_signed32(rs1) < to_signed32(rs2) else 0


def sltu(rs1: int, rs2: int) -> int:
    return 1 if to_unsigned32(rs1) < to_unsigned32(rs2) else 0


def and_(rs1: int, rs2: int) -> int:
    return to_unsigned32(rs1) & to_unsigned32(rs2)


def or_(rs1: int, rs2: int) -> int:
    return to_unsigned32(rs1) | to_unsigned32(rs2)


def xor_(rs1: int, rs2: int) -> int:
    return to_unsigned32(rs1) ^ to_unsigned32(rs2)


I_OPS = {
    "add": add, "sub": sub, "sll": sll, "srl": srl, "sra": sra,
    "slt": slt, "sltu": sltu, "and": and_, "or": or_, "xor": xor_,
}


def apply_i(op: str, rs1: int, rs2: int) -> int:
    try:
        return I_OPS[op.lower()](rs1, rs2)
    except KeyError as e:
        raise ValueError(f"instrução RV32I desconhecida: {op!r}") from e


# --------------------------------------------------------------------------
# Valores de borda usados pelos testes (FR-RV-22)
# --------------------------------------------------------------------------

EDGE_VALUES = [
    0x00000000,          # zero
    0x00000001,          # 1
    0xFFFFFFFF,          # -1
    0x00000002,
    0xFFFFFFFE,          # -2
    0x7FFFFFFF,          # maior positivo (INT32_MAX)
    0x80000000,          # menor negativo (INT32_MIN)
    0x0000FFFF,
    0xFFFF0000,
    0x12345678,
    0xDEADBEEF,
    0x55555555,
    0xAAAAAAAA,
]
