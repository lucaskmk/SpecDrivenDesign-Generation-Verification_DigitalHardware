"""Testbench cocotb com ROM e RAM virtuais para a entidade ``cpu``.

Protocolo de um ciclo, o mesmo de ``spec-riscv-test/spec_riscv_test/tb_riscv.py``:

1. na borda de descida lê o PC (``instr_addr``) e entrega a instrução em
   ``instr_data``;
2. ``ReadWrite``: o decodificador e o somador de endereço da CPU assentam;
   só então ``data_addr`` pertence a esta instrução, e não à anterior;
3. lê ``data_addr`` e entrega a palavra da RAM em ``data_read_data``;
4. ``ReadWrite``: a resposta assíncrona assenta;
5. amostra ``data_write``, ``data_width``, ``data_addr`` e ``data_write_data``;
6. na borda de subida confirma o store na RAM virtual.

O relatório tem o mesmo formato do ``tb_generic`` (``falhas`` com ``tipo``,
``erro`` como dicionário), que é o que ``rvverify.feedback`` sabe ler.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import FallingEdge, ReadWrite, RisingEdge, Timer

from .memmap import RAM_BASE, RAM_BYTES

MASK32 = 0xFFFFFFFF
HALT_CICLOS = 3          # ciclos seguidos no auto-laço para dar o programa por terminado
MAX_AVISOS = 8


class _Indefinido(AssertionError):
    """Uma saída da CPU não tem valor 0/1 quando o testbench precisou dela."""


def _spec() -> dict:
    return json.loads(Path(os.environ["RVVERIFY_SPEC"]).read_text(encoding="utf-8"))


def _write(path: str, payload: dict) -> None:
    Path(path).write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _int(sinal, nome: str, ciclo: int) -> int:
    try:
        return int(sinal.value)
    except ValueError:
        raise _Indefinido(f"{nome} tem valor indefinido ({sinal.value}) no ciclo {ciclo}") from None


def _guardar(ram: dict[int, int], endereco: int, largura: int, valor: int) -> None:
    """Aplica um store (largura 0=byte, 1=meia palavra, 2=palavra) na palavra de ``endereco``."""
    alinhado = endereco & ~3
    antigo = ram.get(alinhado, 0)
    if largura == 0:
        deslocamento = (endereco & 3) * 8
        mascara, valor = 0xFF << deslocamento, (valor & 0xFF) << deslocamento
    elif largura == 1:
        deslocamento = (endereco & 2) * 8
        mascara, valor = 0xFFFF << deslocamento, (valor & 0xFFFF) << deslocamento
    elif largura == 2:
        mascara = MASK32
    else:
        raise AssertionError(f"data_width inválido em um store: {largura}")
    ram[alinhado] = ((antigo & ~mascara) | valor) & MASK32


@cocotb.test()
async def run_program(dut):
    spec = _spec()
    nome = spec.get("name", "<sem nome>")
    words = [int(x) & MASK32 for x in spec["program_words"]]
    ram_base = int(spec.get("ram_base", RAM_BASE))
    ram_fim = ram_base + int(spec.get("ram_bytes", RAM_BYTES))
    halt = {int(x) for x in spec.get("halt_pcs", [])}
    max_ciclos = int(spec.get("max_cycles", 20000))
    ram: dict[int, int] = {}
    visitas: Counter[int] = Counter()
    avisos: list[str] = []
    payload: dict = {"name": nome, "resultado": "falhou", "falhas": [], "erro": None,
                     "cycles": 0, "instructions": None, "avisos": avisos}
    ciclo = 0
    try:
        if spec.get("expect_regs"):
            payload["erro"] = {"tipo": "observacao", "mensagem":
                               "o modo virtual não observa registradores; "
                               "só a RAM virtual é conferida"}
            raise AssertionError(payload["erro"]["mensagem"])

        cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())
        dut.rst.value = 1
        dut.instr_data.value = 0
        dut.data_read_data.value = 0
        await Timer(1, unit="ns")
        for _ in range(3):
            await RisingEdge(dut.clk)
        dut.rst.value = 0

        parado = 0
        for ciclo in range(1, max_ciclos + 1):
            await FallingEdge(dut.clk)
            pc = _int(dut.instr_addr, "instr_addr", ciclo) & MASK32
            visitas[pc] += 1
            indice = pc // 4
            dut.instr_data.value = words[indice] if pc % 4 == 0 and 0 <= indice < len(words) else 0

            # a instrução e assíncrona: deixe o decodificador assentar antes de
            # amostrar o pedido de dados, senão a resposta é da instrução anterior
            await ReadWrite()
            endereco = _int(dut.data_addr, "data_addr", ciclo) & MASK32
            dut.data_read_data.value = ram.get(endereco & ~3, 0)
            await ReadWrite()

            escreve = _int(dut.data_write, "data_write", ciclo)
            if escreve:
                largura = _int(dut.data_width, "data_width", ciclo)
                endereco_escrita = _int(dut.data_addr, "data_addr", ciclo) & MASK32
                valor = _int(dut.data_write_data, "data_write_data", ciclo) & MASK32
            await RisingEdge(dut.clk)

            if escreve:
                if ram_base <= (endereco_escrita & ~3) < ram_fim:
                    _guardar(ram, endereco_escrita, largura, valor)
                elif len(avisos) < MAX_AVISOS:
                    avisos.append(f"store fora da RAM [{ram_base:#x}, {ram_fim:#x}) ignorado: "
                                  f"{endereco_escrita:#010x} no ciclo {ciclo}")

            parado = parado + 1 if pc in halt else 0
            if parado >= HALT_CICLOS:
                break
        else:
            payload["erro"] = {"tipo": "travamento", "mensagem":
                               f"a CPU não chegou ao auto-laço em {max_ciclos} ciclos",
                               "dados": {"max_ciclos": max_ciclos,
                                         "pcs_mais_visitados": [[p, n] for p, n in visitas.most_common(3)],
                                         "enderecos_de_parada": sorted(halt),
                                         "pc_observavel": True}}
            raise AssertionError(payload["erro"]["mensagem"])

        payload["cycles"] = ciclo
        for chave, esperado in sorted(spec.get("expect_ram", {}).items(), key=lambda kv: int(kv[0], 0)):
            endereco = int(chave, 0)
            querido, obtido = int(esperado) & MASK32, ram.get(endereco & ~3, 0)
            if obtido != querido:
                payload["falhas"].append({"tipo": "ram", "endereco": endereco,
                                          "esperado": querido, "obtido": obtido})
        despejo = spec.get("dump_ram")
        if despejo:
            inicio = int(despejo["start"])
            payload["ram_dump"] = {hex(inicio + 4 * i): ram.get(inicio + 4 * i, 0)
                                   for i in range(int(despejo["count"]))}
        for aviso in avisos:
            cocotb.log.warning(aviso)
        if payload["falhas"]:
            raise AssertionError(f"[{nome}] {len(payload['falhas'])} posição(ões) da RAM "
                                 f"diferente(s) do esperado")
        payload["resultado"] = "passou"
    except AssertionError as erro:
        payload["cycles"] = payload["cycles"] or ciclo
        if payload["erro"] is None and not payload["falhas"]:
            payload["erro"] = {"tipo": "interno", "mensagem": str(erro)}
        raise
    except BaseException as erro:
        payload["cycles"] = payload["cycles"] or ciclo
        payload["erro"] = {"tipo": "interno", "mensagem": f"{type(erro).__name__}: {erro}"}
        raise
    finally:
        _write(spec["report_out"], payload)
