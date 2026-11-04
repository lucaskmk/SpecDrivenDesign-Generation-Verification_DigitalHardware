"""Mapa de memória do validador: a única definição.

A ROM virtual começa em 0 e a RAM virtual fica em ``RAM_BASE``, com
``RAM_BYTES`` bytes. O ``cpu.toml`` repete esses valores em ``[memory]`` e o
``rvverify`` os repassa ao testbench; o ``rvgen`` os usa ao gerar o manifesto.
Escritas fora da RAM não são guardadas.

O ``spec-riscv-test`` não usa este mapa: a memória dele é plana e vem do ELF
dos programas oficiais.
"""

RAM_BASE = 0x00FC8100
RAM_BYTES = 512

__all__ = ["RAM_BASE", "RAM_BYTES"]
