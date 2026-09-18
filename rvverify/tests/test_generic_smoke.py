#!/usr/bin/env python3
"""Prova de ponta a ponta do caminho GENERICO do validador.

REQ: FR-RV-21 (execucao real com exit code), FR-RV-22, NFR-RV-01, NFR-RV-02.

Diferente de `test_manifest.py`, este teste roda GHDL de verdade. E ele nao
passa por nenhum adaptador: monta o programa, escreve o JSON do caso e chama
`rvverify.builder` + `rvverify.tb_generic` direto, exatamente como fara uma
CPU nova que so entregou um `cpu.toml`. Se o caminho generico quebrar, este
teste quebra mesmo com a suite da CPU pipeline inteira verde.

O montador vem de `rvverify/asm.py` -- e a unica coisa que este
teste toma emprestado do exemplo; o validador em si nao depende dele.

Pulado automaticamente quando nao ha GHDL na maquina.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
EXAMPLE = REPO_ROOT / "cpus" / "rv32i_pipeline"
TOOLS = EXAMPLE / "tools"
for p in (REPO_ROOT, TOOLS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

pytestmark = pytest.mark.skipif(
    shutil.which("ghdl") is None,
    reason="GHDL nao esta no PATH; o caminho generico exige simulador real",
)

RAM_BASE = 0x00FC8100

PROGRAMA = f"""
# REQ: FR-RV-22 -- soma simples publicada na RAM
    li   x5, 7
    li   x6, 35
    add  x7, x5, x6
    li   x11, {RAM_BASE}
    sw   x7, 0(x11)
halt:
    j    halt
"""


def test_cpu_com_manifesto_roda_no_caminho_generico(tmp_path):
    """Manifesto -> build -> tb_generic -> relatorio, sem adaptador no meio."""
    from rvverify.asm import assemble_with_symbols, find_halt_addresses, write_ram_image
    from rvverify.builder import build_design, run_simulation
    from rvverify.manifest import load_manifest

    manifest = load_manifest(EXAMPLE / "cpu.toml")

    words, _ = assemble_with_symbols(PROGRAMA, base_address=0, allow_m=False)
    halt_pcs = find_halt_addresses(words)
    assert halt_pcs, "o programa precisa terminar em auto-laco (ADR-003)"
    image = write_ram_image(words, tmp_path / "smoke.ram", header="smoke generico")

    report = tmp_path / "report.json"
    spec = {
        "manifest": str(manifest.path),
        "name": "smoke_generico",
        "requirements": ["FR-RV-21", "FR-RV-22"],
        "max_cycles": 500,
        "halt_pcs": halt_pcs,
        "expect_regs": {"7": 42},
        "expect_ram": {hex(RAM_BASE): 42},
        "dump_ram": {"start": RAM_BASE, "count": 2},
        "report_out": str(report),
    }
    spec_path = tmp_path / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    built = build_design(manifest)
    run_simulation(
        built,
        test_module="rvverify.tb_generic",
        parameters={
            manifest.program.generic: str(image),
            manifest.program.size_generic: manifest.program.size_words,
        },
        extra_env={"RVVERIFY_SPEC": str(spec_path)},
    )

    data = json.loads(report.read_text(encoding="utf-8"))

    # -- a execucao terminou pelo criterio do manifesto -------------------
    assert data["halted"] is True
    assert data["halt_mode"] == "commit_pc"
    assert data["halt_pc"] == halt_pcs[0]
    assert data["cycles"] > 0

    # -- o resultado funcional foi lido pelos caminhos declarados ---------
    assert data["ram_dump"][hex(RAM_BASE)] == 42
    assert data["registers"][7] == 42
    assert data["registers"][0] == 0

    # -- este manifesto observa tudo, entao nada fica null ----------------
    assert data["observability"]["unobserved"] == []
    assert data["instructions"] is not None
    assert data["cpi"] is not None
    assert data["m_dispatches"] == 0            # programa sem RV32M
