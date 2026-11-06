#!/usr/bin/env python3
"""Testes do `rvgen gerar --evoluir-de`, com modelo e executor falsos.

Cenário: uma CPU RV32I gerada e aprovada vira RV32IM. Confere a ordem que o
professor pediu (rodar tudo e entender as specs antes de mudar), que só os
blocos do plano mudam e que o juiz final roda na ISA nova.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from rvgen import evolucao as evo
from rvgen.agente import Agente, ErroGeracao
from rvgen.tests.test_agente import PLANO_VALIDO, ExecutorFalso, ModeloFalso, ok, vhdl


class ModeloEvolucao(ModeloFalso):
    """O modelo falso de sempre, mais as duas chamadas da evolução."""

    def _fase(self, texto: str) -> tuple[str, str]:
        if "plan the SMALLEST change" in texto:
            return "plano_evolucao", "-"
        if "Update the semantic contract for component" in texto:
            m = re.search(r"component `([^`]+)`", texto)
            # mesma resposta (Markdown com as seis seções) da revisão de contrato
            return "revisao_especificacao", m.group(1) if m else "-"
        return super()._fase(texto)


COMPONENTE_OK = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}


class TestEvoluir(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.linhas: list[str] = []

    def tearDown(self):
        self._tmp.cleanup()

    def agente(self, modelo, executor, pasta: Path, isa: str) -> Agente:
        return Agente(cliente=modelo, executor=executor, pasta=pasta,
                      microarquitetura="monociclo", isa=isa, iteracoes=3,
                      relatar=self.linhas.append, protegidos=lambda: "selo",
                      caso_de_fumaca=lambda: "simple", max_casos_teste=1,
                      testes_componentes=True, gates_componentes=True)

    def origem_rv32i(self) -> Path:
        origem = self.raiz / "origem"
        r = self.agente(ModeloFalso({"decomposicao": [PLANO_VALIDO]}),
                        ExecutorFalso([ok(1), ok(40)] * 3, [COMPONENTE_OK] * 40),
                        origem, "rv32i").gerar()
        self.assertTrue(r.objetivo_atingido)
        return origem

    def evoluir(self, plano: dict, escritas: list[str] | None = None):
        origem = self.origem_rv32i()
        roteiro = {"plano_evolucao": [json.dumps(plano)]}
        if escritas:
            roteiro["escrita"] = list(escritas)
        modelo = ModeloEvolucao(roteiro)
        ex = ExecutorFalso([ok(40)] + [ok(1), ok(48)] * 3, [COMPONENTE_OK] * 60)
        pasta = self.raiz / "evoluida"
        r = evo.evoluir(self.agente(modelo, ex, pasta, "rv32im"), origem)
        return origem, pasta, modelo, ex, r

    def test_roda_tudo_e_entende_antes_de_mudar(self):
        _, _, modelo, ex, _ = self.evoluir(
            {"understanding": "RV32M adds mul/div", "changes": [{"block": "alu", "change": "add M"}]})
        # antes da primeira chamada à IA: os testes de componente de todos os
        # blocos e o juiz na ISA antiga (é a única chamada antes do plano)
        self.assertEqual(modelo.pedidos[0][0], "plano_evolucao")
        antes_do_plano = ex.chamadas[:4]
        self.assertEqual([c.get("componente") for c in antes_do_plano[:3]], ["alu", "regs", "cpu"])
        self.assertEqual(antes_do_plano[3]["etapa"], "rv32i")
        # o plano recebe a linha de base, o diff das specs e as instruções novas
        plano = modelo.pedidos[0][2]
        self.assertIn('"spec_riscv_test": "40/40', plano)
        self.assertIn("RV32M Implementation Reference", plano)
        self.assertIn("mul, mulh, mulhsu, mulhu, div, divu, rem, remu", plano)

    def test_so_o_bloco_do_plano_muda_e_o_juiz_final_e_rv32im(self):
        origem, pasta, modelo, ex, r = self.evoluir(
            {"understanding": "RV32M adds mul/div", "changes": [{"block": "alu", "change": "add M"}]})
        self.assertTrue(r.objetivo_atingido)
        escritas = [(a, p) for f, a, p in modelo.pedidos if f == "escrita"]
        self.assertEqual([a for a, _ in escritas], ["src/alu.vhd"])
        self.assertIn("APPROVED for the previous specification", escritas[0][1])
        # blocos congelados: mesmo VHDL e nenhum testbench novo pedido à IA
        for nome in ("regs", "cpu"):
            self.assertEqual((pasta / "src" / f"{nome}.vhd").read_text(encoding="utf-8"),
                             (origem / "src" / f"{nome}.vhd").read_text(encoding="utf-8"))
        self.assertEqual([a for f, a, _ in modelo.pedidos if f == "testbench"], ["alu"])
        # os testes antigos da alu viraram regressão
        self.assertTrue((r.sessao / "testes_casos" / "alu" / "publicos" / "anterior-test_alu.py").exists())
        # juiz final na ISA nova
        self.assertEqual(ex.chamadas[-1]["etapa"], "rv32im")
        resultado = json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))
        self.assertEqual(resultado["evolucao"]["mudaram"], ["alu"])
        self.assertEqual(resultado["evolucao"]["congelados"], ["cpu", "regs"])
        self.assertEqual(resultado["isa"], "rv32im")
        plano_md = (r.sessao / "evolucao" / "plano.md").read_text(encoding="utf-8")
        self.assertIn("RV32M adds mul/div", plano_md)
        self.assertIn("- `regs`", plano_md)
        arq = json.loads((pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual(arq["isa"], "rv32im")
        self.assertIn("mul", [i["mnemonic"] for i in arq["instructions"]])
        inicio = json.loads((r.sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((inicio["modo"], inicio["isa_anterior"]), ("evoluir", "rv32i"))

    def test_bloco_novo_entra_antes_do_topo_e_o_topo_muda(self):
        _, pasta, modelo, _, r = self.evoluir(
            {"understanding": "separate M unit", "changes": [],
             "new_blocks": [{"name": "muldiv", "responsibility": "RV32M ops",
                             "ports": ["a : in std_logic_vector(31 downto 0)"]}]},
            # o topo reescrito precisa instanciar o bloco novo (checagem de integração)
            escritas=[vhdl("muldiv"), vhdl("cpu").replace(
                "  u_alu :", "  u_muldiv : entity work.muldiv port map ();\n  u_alu :")])
        self.assertTrue(r.objetivo_atingido)
        arq = json.loads((pasta / "architecture.json").read_text(encoding="utf-8"))
        nomes = [b["name"] for b in arq["blocks"]]
        self.assertEqual(nomes[-1], "cpu")
        self.assertIn("muldiv", nomes)
        self.assertIn("muldiv", arq["blocks"][-1]["depends_on"])
        escritas = [a for f, a, _ in modelo.pedidos if f == "escrita"]
        self.assertEqual(sorted(escritas), ["src/cpu.vhd", "src/muldiv.vhd"])
        self.assertTrue((pasta / "src" / "muldiv.vhd").exists())

    def test_sem_sessao_aprovada_e_erro_claro(self):
        vazio = self.raiz / "nada"
        (vazio / ".rvgen" / "sessao-1").mkdir(parents=True)
        with self.assertRaisesRegex(ErroGeracao, "não tem sessão aprovada"):
            evo.sessao_aprovada(vazio)


class TestMontadorNaCpuIM(unittest.TestCase):
    """Rodada real (06/11/2026): o pedido mandava usar `assemble_rv32i`, o validador
    de uma CPU RV32IM só aceitava `assemble_rv32im`, e 30 casos de teste do
    `decoder` foram recusados em sequência até bater o teto de chamadas."""

    def caso(self, montador: str, instrucao: str) -> str:
        return (f"import cocotb\nfrom rvgen.riscv_asm import {montador}\n\n"
                "@cocotb.test()\nasync def test_um(dut):\n"
                f"    programa = {montador}('{instrucao}')\n"
                "    dut.instr.value = programa[0]\n")

    def test_aceita_os_dois_montadores_conferindo_cada_um_na_sua_isa(self):
        with tempfile.TemporaryDirectory() as d:
            agente = Agente(cliente=ModeloFalso(), executor=ExecutorFalso([]), pasta=Path(d),
                            microarquitetura="monociclo", isa="rv32im", relatar=lambda _: None,
                            protegidos=lambda: "selo")
            aceita = lambda codigo: agente._novo_caso_usa_assembly_rv32i(  # noqa: E731
                codigo, {"test_um"}, ["instr"])
            self.assertTrue(aceita(self.caso("assemble_rv32i", "sll x5, x6, x7")))
            self.assertTrue(aceita(self.caso("assemble_rv32im", "mul x5, x6, x7")))
            # `mul` não é RV32I: pelo montador do I, a fonte é inválida
            self.assertFalse(aceita(self.caso("assemble_rv32i", "mul x5, x6, x7")))
            self.assertEqual(agente._montador_de_estimulos(), "assemble_rv32im")


class TestAplicarPlano(unittest.TestCase):
    ARQ = {"blocks": [
        {"name": "alu", "file": "src/alu.vhd", "responsibility": "alu", "ports": ["a : in bit"],
         "depends_on": []},
        {"name": "cpu", "file": "src/cpu.vhd", "responsibility": "top", "ports": [],
         "depends_on": ["alu"]}]}

    def test_portas_do_topo_nao_mudam(self):
        _, _, motivo = evo.aplicar_plano(self.ARQ, {"changes": [
            {"block": "cpu", "change": "x", "ports": ["z : in bit"]}]})
        self.assertIn("não mudam", motivo)

    def test_bloco_inexistente_e_plano_vazio_sao_recusados(self):
        self.assertIn("inexistente", evo.aplicar_plano(
            self.ARQ, {"changes": [{"block": "fpu", "change": "x"}]})[2])
        self.assertIn("não muda nenhum bloco", evo.aplicar_plano(self.ARQ, {"changes": []})[2])

    def test_portas_novas_de_um_bloco_existente(self):
        arq, mudancas, motivo = evo.aplicar_plano(self.ARQ, {"changes": [
            {"block": "alu", "change": "wider op", "ports": ["a : in bit", "op : in bit"]}]})
        self.assertEqual(motivo, "")
        self.assertEqual(mudancas, {"alu": "wider op"})
        self.assertEqual(arq["blocks"][0]["ports"], ["a : in bit", "op : in bit"])


if __name__ == "__main__":
    unittest.main()
