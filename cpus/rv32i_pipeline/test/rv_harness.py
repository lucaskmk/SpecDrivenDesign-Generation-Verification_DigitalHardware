#!/usr/bin/env python3
"""Adaptador: liga esta CPU ao harness generico do `rvverify`.

REQ: FR-RV-21 (reset, clock, teto de ciclos, termino normal, travamento,
exit code), FR-RV-24 (metricas de eficiencia), FR-RV-06 (leitura de
registradores e RAM).

Este arquivo NAO tem mais logica de testbench. Tudo o que era especifico
desta CPU -- os 11 sinais internos lidos pelo nome, o mapa de memoria, o
periodo de clock, a polaridade do reset, o modo de parada -- foi para
`cpus/rv32i_pipeline/cpu.toml`, e a mecanica foi para `rvverify/harness.py`,
que serve qualquer CPU com manifesto.

O que sobra aqui e a API publica que as suites ja usam (`CpuHarness`,
`CpuTimeout`) e as constantes do mapa de memoria, agora DERIVADAS do
manifesto em vez de repetidas a mao.

Detalhes de interface desta CPU (auditoria em `specs/decisions.md`, ADR-000)
estao documentados no proprio cpu.toml, ao lado do campo que os expressa:
  * `rst` e ATIVO EM NIVEL ALTO e assincrono;
  * o banco de registradores escreve na BORDA DE DESCIDA do clock;
  * ROM e RAM tem latencia de leitura ZERO (combinacional);
  * a RAM de dados comeca em DATA_RAM_BASE_ADDRESS = 0x00FC8100.
"""

from __future__ import annotations

import sys
from pathlib import Path

_EXAMPLE_ROOT = Path(__file__).resolve().parent.parent
_REPO_ROOT = _EXAMPLE_ROOT.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from rvverify.harness import (  # noqa: E402
    HALT_BEQ_SELF,
    HALT_ENCODINGS,
    HALT_JAL_SELF,
    CpuTimeout,
    ObservationError,
    RunMetrics,
)
from rvverify.harness import CpuHarness as _GenericCpuHarness  # noqa: E402
from rvverify.manifest import load_manifest  # noqa: E402

__all__ = [
    "CpuHarness",
    "CpuTimeout",
    "ObservationError",
    "RunMetrics",
    "MANIFEST",
    "MANIFEST_PATH",
    "DATA_RAM_BASE_ADDRESS",
    "DATA_RAM_SIZE_BYTES",
    "DATA_ROM_BASE_ADDRESS",
    "CLOCK_PERIOD_NS",
    "HALT_DRAIN_CYCLES",
    "HALT_ENCODINGS",
    "HALT_JAL_SELF",
    "HALT_BEQ_SELF",
]

MANIFEST_PATH = _EXAMPLE_ROOT / "cpu.toml"
MANIFEST = load_manifest(MANIFEST_PATH)

# Constantes do mapa de memoria -- vem do manifesto, que por sua vez copia
# memory_package.vhd. Nenhuma delas e redigitada aqui.
DATA_RAM_BASE_ADDRESS = MANIFEST.memory.ram_base
DATA_RAM_SIZE_BYTES = MANIFEST.memory.ram_bytes
DATA_ROM_BASE_ADDRESS = 0x00FC8000        # DATA_MEMORY_BASE_ADDRESS
CLOCK_PERIOD_NS = MANIFEST.clock.period_ns
HALT_DRAIN_CYCLES = MANIFEST.halt.drain


class CpuHarness(_GenericCpuHarness):
    """Harness generico ja amarrado ao manifesto desta CPU.

    Existe so para preservar a assinatura `CpuHarness(dut)` que os modulos
    cocotb desta trilha (`tb_program.py`, `tb_snapshot.py`) usam.
    """

    def __init__(self, dut, clock_period_ns: int | None = None):
        super().__init__(dut, MANIFEST, clock_period_ns=clock_period_ns)
