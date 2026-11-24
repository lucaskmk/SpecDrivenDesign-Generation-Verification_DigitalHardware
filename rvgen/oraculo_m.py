"""Oráculo do M para classificar mutantes sobreviventes (`rvgen mutacao`).

Teste cocotb, sem IA, que compara um bloco que calcula as 8 operações do M
com um modelo Python da ISA (RISC-V Unprivileged, extensão M) em todos os
pares de 16 valores de borda (zero, ±1, ±2^31, padrões alternados...). Um
mutante que nenhum nível de teste matou e que este oráculo também não mata é
tratado como equivalente; um que o oráculo mata é um defeito real que nem os
testes gerados nem o `riscv-tests` pegam.

Serve a blocos com `operand_a`, `operand_b`, `result` e o seletor em `funct3`
(3 bits) ou em `instr` (instrução R-type completa).
"""

from __future__ import annotations

import cocotb
from cocotb.triggers import Timer

from rvgen.referencia_m import VALORES, referencia


@cocotb.test()
async def oraculo_m(dut):
    erros = []
    for f3 in range(8):
        for a in VALORES:
            for b in VALORES:
                if hasattr(dut, "funct3"):
                    dut.funct3.value = f3
                else:
                    dut.instr.value = (0b0000001 << 25) | (f3 << 12) | 0x33
                dut.operand_a.value = a
                dut.operand_b.value = b
                await Timer(1, unit="ns")
                obtido = int(dut.result.value)
                esperado = referencia(f3, a, b)
                if obtido != esperado:
                    erros.append(f"funct3={f3} a=0x{a:08X} b=0x{b:08X}: "
                                 f"esperado 0x{esperado:08X}, obtido 0x{obtido:08X}")
    assert not erros, f"{len(erros)} divergencias; primeiras: {erros[:5]}"
