#!/usr/bin/env python3
"""Teste de integracao opcional do runner de componentes no Docker real.

Execute explicitamente com ``RVGEN_TEST_DOCKER=1``. Ele nao depende de LLM nem
de uma CPU gerada: valida a fronteira GHDL + cocotb + import do testbench que
o fluxo ``--testes-componentes`` usa.
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

from rvgen.config import IMAGEM_DOCKER_PADRAO, REPO_ROOT
from rvgen.executor import ExecutorDocker


@unittest.skipUnless(os.environ.get("RVGEN_TEST_DOCKER") == "1",
                     "defina RVGEN_TEST_DOCKER=1 para rodar GHDL+cocotb no Docker")
class TestComponentRunnerDocker(unittest.TestCase):
    def test_compila_importa_e_executa_testbench(self):
        """O modulo cocotb e encontrado sem perder a biblioteca GHDL de build."""
        with tempfile.TemporaryDirectory(prefix=".rvgen-component-smoke-", dir=REPO_ROOT) as d:
            raiz = Path(d)
            (raiz / "src").mkdir()
            (raiz / "src" / "component_smoke.vhd").write_text("""\
library ieee;
use ieee.std_logic_1164.all;
entity component_smoke is
  port (a : in std_logic; y : out std_logic);
end entity;
architecture rtl of component_smoke is begin y <= a; end architecture;
""", encoding="utf-8")
            (raiz / "cpu.toml").write_text("""\
[design]
name = "component_smoke"
top = "component_smoke"
std = "08"
sources = ["src/component_smoke.vhd"]
[clock]
signal = "clk"
period_ns = 10
[reset]
signal = "rst"
active = "high"
[memory]
ram_base = 0x00FC8100
ram_bytes = 4
[observe]
ram = "ram"
[halt]
mode = "fetch_pc"
pc = "pc"
""", encoding="utf-8")
            teste = raiz / "test_component_smoke.py"
            teste.write_text("""\
import cocotb
from cocotb.triggers import Timer

@cocotb.test()
async def combinacional(dut):
    dut.a.value = 1
    await Timer(1, unit="ns")
    assert int(dut.y.value) == 1
""", encoding="utf-8")
            relatorio = raiz / "resultado.json"
            ex = ExecutorDocker(IMAGEM_DOCKER_PADRAO, REPO_ROOT).rodar_componente(
                raiz, componente="component_smoke", teste=teste,
                json_saida=relatorio, workdir=raiz / "sim", build_root=raiz / "build",
                fontes=[raiz / "src" / "component_smoke.vhd"],
                timeout=120)
            rel = json.loads(relatorio.read_text(encoding="utf-8"))
        self.assertEqual(ex.codigo, 0, ex.saida)
        self.assertTrue(rel["compilacao"]["ok"])
        self.assertTrue(rel["passed"], rel)
