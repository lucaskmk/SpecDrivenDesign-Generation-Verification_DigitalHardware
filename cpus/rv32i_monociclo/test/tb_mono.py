#!/usr/bin/env python3
"""Testbench cocotb da CPU monociclo: clock, reset, execução e despejo de estado.

REQ: FR-RV-06, FR-RV-15, FR-RV-21, FR-RV-24

Este módulo é autossuficiente de propósito: ele NÃO importa nada de
`examples/RISCV32I/test/` nem do pacote `rvverify`. O objetivo desta CPU é ser
a prova de que o mecanismo de conformidade não está preso a um design; um
smoke test que dependesse do outro design ou do validador em construção não
provaria nada.

O caso de teste chega por um JSON apontado pela variável de ambiente
`RV_MONO_SPEC`. O testbench executa e devolve o estado observado (registradores,
faixa de RAM, métricas) em outro JSON. Quem compara com o modelo de referência
é o pytest, em `test_monociclo.py` — aqui não há valor esperado escrito à mão.

Detecção de parada (`fetch_pc`)
-------------------------------
Num monociclo o salto é resolvido no mesmo ciclo da busca, então o PC de busca
fica ESTACIONÁRIO no auto-laço `halt: j halt`. Basta observar `pc`. O
testbench ainda confirma a estacionariedade por alguns ciclos de dreno, para
que um PC que apenas passe pelo endereço não seja confundido com uma parada.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer

CLOCK_PERIOD_NS = 10
SETTLE_NS = 1  # tempo para a lógica combinacional assentar após a borda


def _safe_int(handle) -> int | None:
    """Lê um sinal tolerando metavalores ('U'/'X') dos primeiros ciclos."""
    try:
        return int(handle.value)
    except Exception:  # noqa: BLE001
        return None


def _bit(handle) -> int | None:
    s = str(handle.value)
    return int(s) if s in ("0", "1") else None


class MonoHarness:
    """Dirige a CPU monociclo e observa seu estado arquitetural."""

    def __init__(self, dut, spec: dict):
        self.dut = dut
        self.spec = spec
        self.ram_base = int(spec.get("ram_base", 0x00FC8100))
        self.ram_bytes = int(spec.get("ram_bytes", 512))

    # -- infraestrutura ---------------------------------------------------

    async def reset(self, cycles: int = 3) -> None:
        """Reset assíncrono ativo em ALTO (FR-RV-15).

        Termina com o reset já liberado e a primeira instrução do programa
        assentada nas saídas combinacionais, mas AINDA NÃO comitada — de modo
        que o laço de execução consegue amostrar o ciclo 1.
        """
        self.dut.rst.value = 1
        cocotb.start_soon(Clock(self.dut.clk, CLOCK_PERIOD_NS, unit="ns").start())
        for _ in range(cycles):
            await RisingEdge(self.dut.clk)
        # solta o reset longe das bordas
        await Timer(CLOCK_PERIOD_NS // 4, unit="ns")
        self.dut.rst.value = 0
        await Timer(SETTLE_NS, unit="ns")

    # -- observação de estado ---------------------------------------------

    def read_reg(self, index: int) -> int:
        """Lê xN. x0 é arquiteturalmente zero, então é devolvido como 0."""
        if not 0 <= index <= 31:
            raise ValueError(f"registrador fora da faixa: x{index}")
        if index == 0:
            return 0
        v = _safe_int(self.dut.register_file.registers[index])
        return 0 if v is None else v

    def read_all_regs(self) -> list[int]:
        return [self.read_reg(i) for i in range(32)]

    def read_reg0_raw(self) -> int:
        """Lê a posição 0 do array de registradores SEM o atalho arquitetural.

        Serve para provar que nem sequer o armazenamento de x0 foi escrito
        (FR-RV-04), e não apenas que a leitura é mascarada.
        """
        v = _safe_int(self.dut.register_file.registers[0])
        return 0 if v is None else v

    def read_ram_word(self, byte_addr: int) -> int:
        if byte_addr % 4 != 0:
            raise ValueError(f"endereço de RAM não alinhado: {byte_addr:#x}")
        offset = byte_addr - self.ram_base
        if not 0 <= offset < self.ram_bytes:
            raise ValueError(
                f"endereço {byte_addr:#x} fora da RAM de dados "
                f"[{self.ram_base:#x}, {self.ram_base + self.ram_bytes:#x})"
            )
        v = _safe_int(self.dut.data_memory.data_ram.memory[offset // 4])
        return 0 if v is None else v

    @property
    def pc(self) -> int | None:
        return _safe_int(self.dut.pc)

    # -- execução ---------------------------------------------------------

    async def run_until_halt(self, halt_pcs: set[int], max_cycles: int,
                             drain: int = 2) -> dict:
        """Executa até o PC de busca parar num endereço de auto-laço.

        Devolve as métricas observadas. Num monociclo cada ciclo retira
        exatamente uma instrução, logo `instructions == cycles` e o CPI é 1
        por construção — o testbench devolve as duas contagens para que o
        pytest possa verificar essa afirmação em vez de acreditar nela.
        """
        cycles = 0
        instructions = 0
        m_dispatches = 0
        halt_pc: int | None = None

        m_dispatch = getattr(self.dut, "m_dispatch", None)

        while cycles < max_cycles:
            await Timer(SETTLE_NS, unit="ns")
            pc = self.pc
            if pc is not None and pc in halt_pcs:
                halt_pc = pc
                break

            if m_dispatch is not None and _bit(m_dispatch) == 1:
                m_dispatches += 1

            await RisingEdge(self.dut.clk)
            cycles += 1
            instructions += 1

        if halt_pc is None:
            raise AssertionError(
                f"TRAVAMENTO: a CPU não parou em {max_cycles} ciclos "
                f"(último PC observado: {self.pc!r}, endereços de parada: "
                f"{sorted(hex(p) for p in halt_pcs)}). Requisito: FR-RV-21"
            )

        # dreno: confirma que o PC ficou mesmo estacionário (modo fetch_pc)
        for _ in range(drain):
            await RisingEdge(self.dut.clk)
            await Timer(SETTLE_NS, unit="ns")
            if self.pc != halt_pc:
                raise AssertionError(
                    f"o PC não ficou estacionário no auto-laço: parou em "
                    f"{halt_pc:#010x} e saiu para {self.pc!r}. O modo de parada "
                    f"`fetch_pc` do manifesto não vale para esta CPU."
                )

        return {
            "cycles": cycles,
            "instructions": instructions,
            "cpi": round(cycles / instructions, 6) if instructions else None,
            "m_dispatches": m_dispatches,
            "halt_pc": halt_pc,
            "drain_cycles": drain,
            "clock_period_ns": CLOCK_PERIOD_NS,
            "cycles_method":
                "ciclos do fim do reset ate o PC de busca ficar estacionario "
                "no auto-laco (modo fetch_pc); os ciclos de dreno NAO entram",
            "instructions_method":
                "um por ciclo, por construcao da microarquitetura monociclo",
        }


@cocotb.test()
async def run_program(dut):
    """Aplica reset, executa o programa e despeja o estado arquitetural."""
    spec_path = os.environ.get("RV_MONO_SPEC")
    if not spec_path:
        raise RuntimeError("variável de ambiente RV_MONO_SPEC não definida")
    spec = json.loads(Path(spec_path).read_text(encoding="utf-8"))

    name = spec.get("name", "<sem nome>")
    cocotb.log.info(f"programa: {name}")
    cocotb.log.info(f"requisitos cobertos: {', '.join(spec.get('requirements', []))}")
    cocotb.log.info(f"imagem .ram: {spec.get('image')}")

    harness = MonoHarness(dut, spec)
    await harness.reset(int(spec.get("reset_cycles", 3)))

    # o reset tem de deixar x0 em zero e o PC no vetor de reset (FR-RV-15)
    assert harness.read_reg(0) == 0, "x0 deve ser zero após o reset (FR-RV-04)"
    pc0 = harness.pc
    assert pc0 == 0, f"após o reset o PC deveria ser 0x00000000, é {pc0!r} (FR-RV-15)"

    metrics = await harness.run_until_halt(
        halt_pcs={int(p) for p in spec.get("halt_pcs", [])},
        max_cycles=int(spec.get("max_cycles", 20000)),
        drain=int(spec.get("drain", 2)),
    )

    cocotb.log.info(f"[{name}] parou em {metrics['halt_pc']:#010x} após "
                    f"{metrics['cycles']} ciclos")

    dump_words = int(spec.get("dump_ram_words", harness.ram_bytes // 4))
    payload = {
        "name": name,
        "metrics": metrics,
        "registers": harness.read_all_regs(),
        "x0_storage": harness.read_reg0_raw(),
        "ram": {hex(harness.ram_base + 4 * i): harness.read_ram_word(harness.ram_base + 4 * i)
                for i in range(dump_words)},
    }
    out = spec["state_out"]
    Path(out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    cocotb.log.info(f"estado gravado em {out}")
