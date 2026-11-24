#!/usr/bin/env python3
"""Laço de correção do juiz: não desistir com rodadas sobrando e usar a
checagem de interfaces como evidência. Modelo e executor falsos; sem GHDL."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from rvgen.agente import Agente
from rvgen.executor import Execucao
from rvgen.tests.test_agente import ExecutorFalso, ModeloFalso
from rvgen.tests.test_interfaces import ALU, CONTROLE, TOPO


class Escolheu(Exception):
    """Sinal de que o laço seguiu para a escolha clássica do arquivo."""


class TestLacoDoJuiz(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "gerada"

    def tearDown(self):
        self._tmp.cleanup()

    def agente(self):
        a = Agente(cliente=ModeloFalso(), executor=ExecutorFalso([]), pasta=self.pasta,
                   microarquitetura="monociclo", isa="rv32im", iteracoes=12,
                   relatar=lambda _: None, protegidos=lambda: "selo",
                   caso_de_fumaca=lambda: "rv32i/add")
        a.sessao.mkdir(parents=True)
        return a

    def test_investigacao_esgotada_nao_encerra_com_rodadas_sobrando(self):
        a = self.agente()
        falha = Execucao([], 1, {"status": "failed", "passed": 1, "executed": 48}, "", 1.0,
                         a.sessao / "r.json")
        arq = {"blocks": [{"name": "alu", "file": "src/alu.vhd"},
                          {"name": "cpu", "file": "src/cpu.vhd"}]}
        chamadas = []

        def escolher(evidencia, arq_):
            chamadas.append(evidencia)
            raise Escolheu

        with mock.patch.multiple(
                a, _validar=lambda *x, **k: falha, _objetivo=lambda *x: False,
                _gerar_regressoes_oficiais=lambda *x: [],
                _proxima_regressao_oficial=lambda *x: "rv32ui-p-add",
                _validar_regressoes_oficiais=lambda *x: (True, ""),
                _evidencia=lambda *x: (None, "falha oficial"),
                _estado_exploracao_cpu=lambda *x: (a.sessao / "e.json", {"ativado": True}),
                _salvar_estado_exploracao_cpu=lambda *x: None,
                _capturar_execucao_oficial_focal=lambda *x: {},
                _explorar_cpu_superior=lambda *x: (False, True, "hipoteses refutadas", None),
                _escolher=escolher):
            with self.assertRaises(Escolheu):
                a._corrigir(arq)
        self.assertEqual(len(chamadas), 1)
        self.assertIn("hipoteses refutadas", chamadas[0])
        eventos = (a.sessao / "sessao.jsonl").read_text(encoding="utf-8")
        self.assertIn('"exploracao_cpu_esgotada"', eventos)
        self.assertIn('"continua": true', eventos)

    def test_evidencia_de_interface_aparece_so_com_desencontro(self):
        a = self.agente()
        (a.pasta / "src").mkdir(parents=True, exist_ok=True)
        self.assertEqual(a._evidencia_interfaces(), "")          # sem VHDL, sem problema
        for nome, texto in (("controle", CONTROLE), ("alu", ALU), ("cpu", TOPO)):
            (a.pasta / "src" / f"{nome}.vhd").write_text(texto, encoding="utf-8")
        texto = a._evidencia_interfaces()
        self.assertIn("INTER-BLOCK CODE MISMATCH", texto)
        self.assertIn("`controle.op` emits 111", texto)
        self.assertNotIn("`sel`", texto)                          # aviso do topo nao entra
        (a.pasta / "src" / "alu.vhd").write_text(
            ALU.replace('when "010" =>', 'when "010" | "111" =>'), encoding="utf-8")
        self.assertEqual(a._evidencia_interfaces(), "")


if __name__ == "__main__":
    unittest.main()
