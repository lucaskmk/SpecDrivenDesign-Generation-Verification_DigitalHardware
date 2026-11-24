#!/usr/bin/env python3
"""O gerador com `--rotulos`: contratos e testes citam rótulos do catálogo,
conferidos sem IA. Usa o modelo e o executor falsos de `test_agente`."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rvgen import rotulos as rot
from rvgen.agente import Agente, ErroGeracao
from rvgen.tests.test_agente import ExecutorFalso, ModeloFalso, testbench

CORPO = ("## Timing\ncombinational\n\n## Reset\nnone\n\n## Behavior\nadds\n\n"
         "## Operations\nnone\n\n## Edge cases\nnone\n\n## Test strategy\n- add two values\n")

ALU = {"name": "alu", "file": "src/alu.vhd", "responsibility": "alu",
       "ports": ["a : in std_logic_vector(31 downto 0)"], "satisfies": [], "depends_on": []}
CPU = {"name": "cpu", "file": "src/cpu.vhd", "responsibility": "top",
       "ports": ["clk : in std_logic"], "satisfies": [], "depends_on": ["alu"]}
ARQ = {"blocks": [ALU, CPU]}


def caso(rotulos: str | None) -> str:
    cabeca = f"# CK: {rotulos}\n" if rotulos else ""
    return ("```python\n" + cabeca + "import cocotb\n\n@cocotb.test()\nasync def caso(dut):\n"
            "    assert dut is not None\n```")


class TestAgenteComRotulos(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "gerada"
        self.cat = rot.carregar(Path(__file__).resolve().parents[2] / "specs" / "rotulos.md")

    def tearDown(self):
        self._tmp.cleanup()

    def agente(self, modelo, *, rotulos=True, isa="rv32im"):
        a = Agente(cliente=modelo, executor=ExecutorFalso([]), pasta=self.pasta,
                   microarquitetura="monociclo", isa=isa, rotulos=rotulos,
                   relatar=lambda _: None, protegidos=lambda: "selo",
                   caso_de_fumaca=lambda: "rv32i/add", testes_componentes=True)
        a.sessao.mkdir(parents=True)
        return a

    def eventos(self, agente, nome):
        linhas = (agente.sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines()
        return [d for d in map(json.loads, linhas) if d.get("evento") == nome]

    def test_contrato_sem_labels_e_recusado_e_depois_aceito(self):
        modelo = ModeloFalso({"especificacao_componente": [
            CORPO, CORPO + "\n## Labels\n- CK-INVENTADO\n",
            CORPO + "\n## Labels\n- CK-ADD-BASICO\n- CK-ADD-WRAP\n"]})
        a = self.agente(modelo)
        a._escrever_especificacao(ALU, ARQ)
        self.assertEqual(a._labels_do_bloco(ALU), {"CK-ADD-BASICO", "CK-ADD-WRAP"})
        contrato = a._ler_especificacao(ALU)
        self.assertIn("## Labels\n- CK-ADD-BASICO\n- CK-ADD-WRAP", contrato)
        self.assertEqual(contrato.count("## Labels"), 1)
        recusas = self.eventos(a, "rotulos_recusados")
        self.assertEqual([r["grupo"] for r in recusas], ["contratos", "contratos"])
        self.assertIn("CK-INVENTADO", recusas[1]["motivo"])
        # o catalogo foi para o prompt do redator
        self.assertIn("CK-DIV-OVERFLOW", modelo.pedidos[0][2])

    def test_cpu_tem_de_assumir_o_que_ninguem_assumiu(self):
        resto = sorted(self.cat.cks("rv32im") - {"CK-ADD-BASICO"})
        modelo = ModeloFalso({"especificacao_componente": [
            CORPO + "\n## Labels\n- CK-ADD-BASICO\n",
            CORPO + "\n## Labels\n- CK-PC-MAIS-4\n",
            CORPO + "\n## Labels\n" + "".join(f"- {ck}\n" for ck in resto)]})
        a = self.agente(modelo)
        a._escrever_especificacao(ALU, ARQ)
        a._escrever_especificacao(CPU, ARQ)
        self.assertEqual(a._labels_do_bloco(CPU), set(resto))
        pedido_cpu = [p for f, alvo, p in modelo.pedidos if alvo == "cpu"][0]
        self.assertIn("no other block claimed", pedido_cpu)
        recusa = self.eventos(a, "rotulos_recusados")[0]
        self.assertIn("claimed by no block", recusa["motivo"])

    def test_revisao_do_contrato_preserva_os_labels(self):
        a = self.agente(ModeloFalso({"especificacao_componente": [
            CORPO + "\n## Labels\n- CK-ADD-BASICO\n"]}))
        a._escrever_especificacao(ALU, ARQ)
        a._salvar_especificacao(ALU, CORPO.replace("adds", "adds two operands"))
        contrato = a._ler_especificacao(ALU)
        self.assertIn("adds two operands", contrato)
        self.assertIn("## Labels\n- CK-ADD-BASICO", contrato)

    def test_caso_isolado_exige_ck_do_bloco(self):
        modelo = ModeloFalso({"especificacao_componente": [CORPO + "\n## Labels\n- CK-ADD-BASICO\n"],
                              "caso_publico_isolado": [caso(None), caso("CK-DIV-ZERO"),
                                                       caso("CK-ADD-BASICO")]})
        a = self.agente(modelo)
        a._escrever_especificacao(ALU, ARQ)
        destino = a.sessao / "testes_candidatos" / "alu" / "caso-01.py"
        a._escrever_caso_publico_isolado(ALU, destino, "Behavior: add", None)
        self.assertEqual(rot.ck_do_teste(destino.read_text(encoding="utf-8")), {"CK-ADD-BASICO"})
        motivos = [r["motivo"] for r in self.eventos(a, "rotulos_recusados")]
        self.assertTrue(any("missing `# CK" in m for m in motivos))
        self.assertTrue(any("CK-DIV-ZERO" in m for m in motivos))

    def test_caso_isolado_sem_ck_valido_esgota_as_tentativas(self):
        modelo = ModeloFalso({"especificacao_componente": [CORPO + "\n## Labels\n- CK-ADD-BASICO\n"],
                              "caso_publico_isolado": [caso(None)] * 3})
        a = self.agente(modelo)
        a._escrever_especificacao(ALU, ARQ)
        with self.assertRaises(ErroGeracao):
            a._escrever_caso_publico_isolado(ALU, a.sessao / "c.py", "Behavior: add", None)

    def test_orquestrador_recusa_complete_uma_vez_com_label_sem_teste(self):
        modelo = ModeloFalso({"especificacao_componente": [
            CORPO + "\n## Labels\n- CK-ADD-BASICO\n- CK-ADD-WRAP\n"]})
        a = self.agente(modelo)
        a._escrever_especificacao(ALU, ARQ)
        teste = a._caminho_teste(ALU)
        teste.parent.mkdir(parents=True, exist_ok=True)
        teste.write_text("# CK: CK-ADD-BASICO\nimport cocotb\n\n@cocotb.test()\n"
                         "async def smoke(dut):\n    assert dut is not None\n", encoding="utf-8")
        a.max_casos_teste = 4
        self.assertIsNone(a._decidir_expansao_testbench(ALU, teste))
        chamadas = [f for f, _, _ in modelo.pedidos if f == "orquestracao_expansao_testbench"]
        self.assertEqual(len(chamadas), 2)           # COMPLETE recusado uma vez
        self.assertIn("CK-ADD-WRAP", [p for f, _, p in modelo.pedidos
                                      if f == "orquestracao_expansao_testbench"][0])
        self.assertIn("CK-ADD-WRAP", self.eventos(a, "rotulos_recusados")[0]["motivo"])

    def test_sem_rotulos_nada_muda(self):
        modelo = ModeloFalso({"especificacao_componente": [CORPO]})
        a = self.agente(modelo, rotulos=False)
        a._escrever_especificacao(ALU, ARQ)
        self.assertNotIn("## Labels", modelo.pedidos[0][2])
        self.assertNotIn("## Labels", a._ler_especificacao(ALU))
        self.assertEqual(a._labels_sem_teste(ALU), [])
        self.assertFalse((a.sessao / "sessao.jsonl").exists() and
                         self.eventos(a, "rotulos_recusados"))

    def test_cobertura_no_fim(self):
        modelo = ModeloFalso({"especificacao_componente": [
            CORPO + "\n## Labels\n- CK-ADD-BASICO\n- CK-ADD-WRAP\n"]})
        a = self.agente(modelo)
        a._escrever_especificacao(ALU, ARQ)
        teste = a._caminho_teste(ALU)
        teste.parent.mkdir(parents=True, exist_ok=True)
        teste.write_text("# CK: CK-ADD-BASICO\n", encoding="utf-8")
        resumo = a._cobertura_rotulos({"blocks": [ALU]})
        self.assertEqual((resumo["cobertos"], resumo["catalogo"]), (1, 50))
        self.assertEqual(resumo["sem_dono"], 48)
        dados = json.loads((a.sessao / "rotulos_cobertura.json").read_text(encoding="utf-8"))
        self.assertEqual(dados["por_bloco"]["alu"]["sem_teste"], ["CK-ADD-WRAP"])


if __name__ == "__main__":
    unittest.main()
