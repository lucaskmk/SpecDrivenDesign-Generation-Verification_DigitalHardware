"""Oráculo do M no nível da CPU (teste cocotb da entidade `cpu`, sem IA).

Monta um programa RV32IM que carrega os 256 pares de 16 valores de borda de
`rvgen.referencia_m` e, para cada par, executa as 8 operações do M e grava
cada resultado na memória com `sw`. O testbench serve a ROM e a RAM pelas
portas fixas de `specs/cpu.md`, captura os stores e compara com o modelo
Python da ISA. Como só usa a entidade `cpu`, vale para qualquer CPU RV32IM do
repositório, seja qual for a decomposição em blocos; o `riscv-tests` só
divide por −1 o próprio −2^31, este programa divide todos os 16 valores.
"""

from __future__ import annotations

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

from rvgen.referencia_m import OPERACOES, programa, referencia
from rvgen.riscv_asm import assemble_rv32im


@cocotb.test()
async def oraculo_m_cpu(dut):
    fonte, esperados = programa()
    rom = assemble_rv32im(fonte)
    parada = max(rom)

    dut.rst.value = 1
    dut.instr_data.value = rom[0]
    dut.data_read_data.value = 0
    cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
    for _ in range(2):
        await RisingEdge(dut.clk)
    await Timer(1, unit="ns")
    dut.rst.value = 0

    memoria: dict[int, int] = {}
    for _ in range(len(rom) + 64):
        pc = int(dut.instr_addr.value)
        assert pc in rom, f"PC fora do programa: 0x{pc:08X}"
        dut.instr_data.value = rom[pc]
        await Timer(1, unit="ns")
        if pc == parada:
            break
        if int(dut.data_write.value) == 1:
            memoria[int(dut.data_addr.value)] = int(dut.data_write_data.value)
        await RisingEdge(dut.clk)
        await Timer(1, unit="ns")
    else:
        raise AssertionError("o programa nao chegou ao laco de parada")

    erros = []
    for endereco, f3, a, b in esperados:
        esperado = referencia(f3, a, b)
        obtido = memoria.get(endereco)
        if obtido != esperado:
            erros.append(f"{OPERACOES[f3]} a=0x{a:08X} b=0x{b:08X}: esperado 0x{esperado:08X}, "
                         f"obtido {'nenhum store' if obtido is None else f'0x{obtido:08X}'}")
    assert not erros, f"{len(erros)} de {len(esperados)} divergencias; primeiras: {erros[:5]}"
