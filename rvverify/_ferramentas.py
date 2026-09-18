#!/usr/bin/env python3
"""Acesso ao montador e ao modelo de referencia do validador.

REQ: FR-RV-19 (montador do projeto), FR-RV-23 (modelo de referencia).

Os dois eram arquivos soltos ao lado da CPU de exemplo e subiram para o
pacote na ADR-013 (`rvverify/asm.py` e `rvverify/reference.py`): sao
infraestrutura do VALIDADOR, nao da CPU de exemplo. Antes, `rvverify`
importava de uma pasta chamada `cpus/`, o que invertia a direcao da
dependencia e quebraria se aquele exemplo saisse.

Este modulo continua existindo como ponto unico de acesso: a suite de
conformidade, o diagnostico e a comparacao de eficiencia usam exatamente o
mesmo montador e o mesmo modelo, sob os nomes historicos `rv_assembler` e
`ref`. Nao ha mais nenhum ajuste de `sys.path` aqui.
"""

from __future__ import annotations

from pathlib import Path

from . import asm as rv_assembler
from . import reference as ref

REPO_ROOT = Path(__file__).resolve().parent.parent

# Os programas de exemplo continuam ao lado da CPU de referencia: sao dados
# de teste daquela CPU, nao codigo do validador.
EXAMPLE_ROOT = REPO_ROOT / "cpus" / "rv32i_pipeline"
PROGRAMS_DIR = EXAMPLE_ROOT / "programs"

__all__ = ["REPO_ROOT", "EXAMPLE_ROOT", "PROGRAMS_DIR", "ref", "rv_assembler"]
