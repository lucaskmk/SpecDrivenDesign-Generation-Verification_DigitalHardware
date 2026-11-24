"""Modelo de referência das 8 operações do M (RISC-V Unprivileged, extensão M).

Python puro; usado pelo oráculo cocotb `rvgen/oraculo_m.py`.
"""

from __future__ import annotations

M32 = 0xFFFFFFFF
MIN = 0x80000000
VALORES = [0, 1, 2, 3, 7, M32, M32 - 1, M32 - 2, (-7) & M32, MIN, MIN + 1, 0x7FFFFFFF,
           0x7FFFFFFE, 0x55555555, 0xAAAAAAAA, 0x12345678]


def _s(x: int) -> int:
    return x - (1 << 32) if x & MIN else x


def _trunc_div(a: int, b: int) -> int:
    q = abs(a) // abs(b)
    return q if (a < 0) == (b < 0) else -q


def referencia(f3: int, a: int, b: int) -> int:
    sa, sb = _s(a), _s(b)
    if f3 == 0:
        return (a * b) & M32
    if f3 == 1:
        return ((sa * sb) >> 32) & M32
    if f3 == 2:
        return ((sa * b) >> 32) & M32
    if f3 == 3:
        return ((a * b) >> 32) & M32
    if f3 == 4:
        if b == 0:
            return M32
        if a == MIN and b == M32:
            return MIN
        return _trunc_div(sa, sb) & M32
    if f3 == 5:
        return M32 if b == 0 else a // b
    if f3 == 6:
        if b == 0:
            return a
        if a == MIN and b == M32:
            return 0
        return (sa - _trunc_div(sa, sb) * sb) & M32
    return a if b == 0 else a % b
