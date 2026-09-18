#!/usr/bin/env python3
"""Acesso ao montador e ao modelo de referencia da CPU de pipeline.

REQ: FR-RV-19 (montador do projeto), FR-RV-23 (modelo de referencia).

Os dois vivem ao lado da CPU de exemplo, fora de qualquer pacote Python.
Este modulo concentra o ajuste de `sys.path` num lugar so, para que a suite
de conformidade, o diagnostico e a comparacao de eficiencia usem exatamente o
mesmo montador e o mesmo modelo.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLE_ROOT = REPO_ROOT / "cpus" / "rv32i_pipeline"
TOOLS_DIR = EXAMPLE_ROOT / "tools"
REFERENCE_DIR = EXAMPLE_ROOT / "test"
PROGRAMS_DIR = EXAMPLE_ROOT / "programs"

for _p in (TOOLS_DIR, REFERENCE_DIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import reference_model as ref  # noqa: E402
import rv_assembler  # noqa: E402

__all__ = ["REPO_ROOT", "EXAMPLE_ROOT", "TOOLS_DIR", "REFERENCE_DIR",
           "PROGRAMS_DIR", "ref", "rv_assembler"]
