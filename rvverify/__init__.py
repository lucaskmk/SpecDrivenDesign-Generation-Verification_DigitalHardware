#!/usr/bin/env python3
"""rvverify -- validador de CPUs RISC-V dirigido por manifesto.

REQ: FR-RV-21, FR-RV-22, FR-RV-24, NFR-RV-01, NFR-RV-02.

A ideia inteira do pacote cabe em uma frase: o testbench nao conhece a CPU,
conhece o `cpu.toml`. Um design entrega o manifesto dizendo como compilar,
como aplicar clock e reset, como carregar o programa, onde estao RAM e
registradores e como reconhecer o termino; o validador faz o resto.

    rvverify.manifest    le e VALIDA o cpu.toml
    rvverify.builder     compila (cache por hash) e dispara o GHDL
    rvverify.harness     harness cocotb parametrizado pelo manifesto
    rvverify.tb_generic  modulo cocotb de top-level

`manifest` nao depende de cocotb e pode ser testado sem hardware nenhum;
`builder`, `harness` e `tb_generic` sao importados sob demanda, para que a
validacao de manifesto continue rodando num ambiente sem simulador.
"""

from __future__ import annotations

from .manifest import (
    HALT_MODES,
    MANIFEST_FILENAME,
    PROGRAM_MODES,
    ClockSpec,
    CpuManifest,
    DesignSpec,
    HaltSpec,
    ManifestError,
    MemorySpec,
    MetricsSpec,
    ObserveSpec,
    ProgramSpec,
    ResetSpec,
    load_manifest,
)

__all__ = [
    "ClockSpec",
    "CpuManifest",
    "DesignSpec",
    "HaltSpec",
    "ManifestError",
    "MemorySpec",
    "MetricsSpec",
    "ObserveSpec",
    "ProgramSpec",
    "ResetSpec",
    "load_manifest",
    "HALT_MODES",
    "PROGRAM_MODES",
    "MANIFEST_FILENAME",
    # carregados sob demanda (exigem cocotb / cocotb_tools):
    "build_design",
    "run_simulation",
    "design_declares_generic",
    "BuiltDesign",
    "CpuHarness",
    "CpuTimeout",
    "ObservationError",
    "RunMetrics",
]

_LAZY = {
    "build_design": ("rvverify.builder", "build_design"),
    "run_simulation": ("rvverify.builder", "run_simulation"),
    "design_declares_generic": ("rvverify.builder", "design_declares_generic"),
    "BuiltDesign": ("rvverify.builder", "BuiltDesign"),
    "CpuHarness": ("rvverify.harness", "CpuHarness"),
    "CpuTimeout": ("rvverify.harness", "CpuTimeout"),
    "ObservationError": ("rvverify.harness", "ObservationError"),
    "RunMetrics": ("rvverify.harness", "RunMetrics"),
}


def __getattr__(name: str):
    """Importa builder/harness so quando alguem realmente pede."""
    target = _LAZY.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    import importlib

    return getattr(importlib.import_module(target[0]), target[1])
