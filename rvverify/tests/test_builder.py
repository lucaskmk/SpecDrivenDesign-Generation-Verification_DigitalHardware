#!/usr/bin/env python3
"""Falha de compilacao vira `BuildFailed` com as linhas do GHDL -- com GHDL real.

REQ: FR-RV-28 (para erro de compilacao, as linhas de erro do GHDL com
arquivo, linha e coluna), NFR-RV-02.

Regressao do defeito achado na primeira execucao real do gerador (TRV-9.8):
com o cocotb 2.0.0 da imagem `spechdl-toolchain`, a falha do `ghdl -m` chega
como `subprocess.CalledProcessError`, que `build_design` nao tratava. A falha
escapava como erro generico, o relatorio a chamava de "manifesto" e as linhas
do GHDL -- exatamente o que quem escreveu a CPU precisa ler -- se perdiam.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

pytest.importorskip("cocotb_tools", reason="cocotb nao instalado neste Python")
pytestmark = pytest.mark.skipif(
    shutil.which("ghdl") is None,
    reason="GHDL nao esta no PATH; a falha real do GHDL e o que esta sob teste",
)

QUEBRADO = """library ieee;
use ieee.std_logic_1164.all;

entity quebrado is
    port(a : in std_logic; y : out std_logic);
end quebrado;

architecture rtl of quebrado is
begin
    y <= a and sinal_que_nao_existe;
end rtl;
"""


def test_erro_do_ghdl_vira_BuildFailed_com_arquivo_e_linha(tmp_path):
    from rvverify.builder import BuildFailed, build_design
    from rvverify.manifest import CpuManifest

    (tmp_path / "quebrado.vhd").write_text(QUEBRADO, encoding="utf-8")
    manifest = CpuManifest.from_dict({
        "design": {"name": "quebrado", "top": "quebrado", "std": "08",
                   "sources": ["quebrado.vhd"]},
        "clock": {"signal": "clk", "period_ns": 10},
        "reset": {"signal": "rst"},
        "memory": {"ram_base": 0x1000, "ram_bytes": 16},
        "observe": {"ram": "ram"},
        "halt": {"mode": "fixed_cycles", "cycles": 1},
    }, tmp_path / "cpu.toml")

    with pytest.raises(BuildFailed) as exc:
        build_design(manifest, build_dir=tmp_path / "build",
                     log_file=tmp_path / "build.log")

    erros = exc.value.errors
    assert erros, f"BuildFailed sem as linhas do GHDL; log:\n{(tmp_path / 'build.log').read_text()}"
    primeiro = erros[0]
    assert primeiro["arquivo"] == "quebrado.vhd"
    assert primeiro["linha"] == 10
    assert "sinal_que_nao_existe" in primeiro["mensagem"]
