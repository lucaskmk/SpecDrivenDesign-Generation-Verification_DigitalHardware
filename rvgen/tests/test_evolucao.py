#!/usr/bin/env python3
"""Testes do `rvgen gerar --evoluir-de`, com modelo e executor falsos.

Cenário: uma CPU RV32I gerada e aprovada (blocos `alu`, `regs`, `cpu`) vira
RV32IM. Confere a ordem que o professor pediu (rodar tudo e entender as specs
antes de mudar), que a decomposição é livre (manter, mudar, criar, juntar,
renomear, remover), que o topo não faz conta e que o juiz final roda na ISA nova.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from rvgen import evolucao as evo
from rvgen.agente import Agente, ErroGeracao, operacoes_aritmeticas_no_topo
from rvgen.tests.test_agente import PLANO_VALIDO, ExecutorFalso, ModeloFalso, ok, vhdl


class ModeloEvolucao(ModeloFalso):
    """O modelo falso de sempre, mais as duas chamadas da evolução."""

    def _fase(self, texto: str) -> tuple[str, str]:
        if "design the target decomposition" in texto:
            return "plano_evolucao", "-"
        if "Update the semantic contract for component" in texto:
            m = re.search(r"component `([^`]+)`", texto)
            # mesma resposta (Markdown com as seis seções) da revisão de contrato
            return "revisao_especificacao", m.group(1) if m else "-"
        return super()._fase(texto)


COMPONENTE_OK = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}


def topo(*blocos: str) -> str:
    """VHDL falso do `cpu` que instancia exatamente estes blocos."""
    instancias = "\n".join(f"  u_{b} : entity work.{b} port map ();" for b in blocos)
    return (f"```vhdl\nentity cpu is\nend cpu;\narchitecture rtl of cpu is\nbegin\n"
            f"{instancias}\nend rtl;\n```")


def plano(entendimento: str, *blocos: dict) -> dict:
    return {"understanding": entendimento, "blocks": list(blocos)}


MANTER = lambda nome: {"name": nome, "action": "keep"}  # noqa: E731


class TestEvoluir(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)
        self.linhas: list[str] = []

    def tearDown(self):
        self._tmp.cleanup()

    def agente(self, modelo, executor, pasta: Path, isa: str, **kw) -> Agente:
        return Agente(cliente=modelo, executor=executor, pasta=pasta,
                      microarquitetura="monociclo", isa=isa, iteracoes=3,
                      relatar=self.linhas.append, protegidos=lambda: "selo",
                      caso_de_fumaca=lambda: "simple", max_casos_teste=1,
                      testes_componentes=True, gates_componentes=True, max_blocos=16, **kw)

    def origem_rv32i(self) -> Path:
        origem = self.raiz / "origem"
        r = self.agente(ModeloFalso({"decomposicao": [PLANO_VALIDO]}),
                        ExecutorFalso([ok(1), ok(40)] * 3, [COMPONENTE_OK] * 40),
                        origem, "rv32i").gerar()
        self.assertTrue(r.objetivo_atingido)
        return origem

    def evoluir(self, plano_json: dict, escritas: list[str] | None = None, **kw):
        origem = self.origem_rv32i()
        roteiro = {"plano_evolucao": [json.dumps(plano_json)]}
        if escritas:
            roteiro["escrita"] = list(escritas)
        modelo = ModeloEvolucao(roteiro)
        ex = ExecutorFalso([ok(40)] + [ok(1), ok(48)] * 3, [COMPONENTE_OK] * 80)
        pasta = self.raiz / "evoluida"
        r = evo.evoluir(self.agente(modelo, ex, pasta, "rv32im", **kw), origem)
        return origem, pasta, modelo, ex, r

    MUDA_ALU = plano("RV32M adds mul/div", {"name": "alu", "action": "change", "change": "add M"},
                     MANTER("regs"), MANTER("cpu"))

    def test_roda_tudo_e_entende_antes_de_mudar(self):
        _, _, modelo, ex, _ = self.evoluir(self.MUDA_ALU)
        # antes da primeira chamada à IA: os testes de componente de todos os
        # blocos e o juiz na ISA antiga
        self.assertEqual(modelo.pedidos[0][0], "plano_evolucao")
        antes_do_plano = ex.chamadas[:4]
        self.assertEqual([c.get("componente") for c in antes_do_plano[:3]], ["alu", "regs", "cpu"])
        self.assertEqual(antes_do_plano[3]["etapa"], "rv32i")
        pedido = modelo.pedidos[0][2]
        self.assertIn('"spec_riscv_test": "40/40', pedido)
        self.assertIn("RV32M Implementation Reference", pedido)
        self.assertIn("mul, mulh, mulhsu, mulhu, div, divu, rem, remu", pedido)
        # a decomposição é livre; a regra do topo só entra se pedida
        self.assertIn("The decomposition is free", pedido)
        self.assertNotIn("must never contain multiplication", pedido)
        self.assertIn("2 to 16 blocks", pedido)
        self.assertNotIn("SMALLEST", pedido)

    def test_com_a_regra_do_topo_o_plano_a_cita(self):
        _, _, modelo, _, r = self.evoluir(self.MUDA_ALU, topo_sem_conta=True)
        pedido = modelo.pedidos[0][2]
        self.assertIn("The decomposition is free", pedido)
        self.assertIn("must never contain multiplication, division, remainder", pedido)
        inicio = json.loads((r.sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertTrue(inicio["topo_sem_conta"])

    def test_so_o_bloco_mudado_e_reescrito_e_o_juiz_final_e_rv32im(self):
        origem, pasta, modelo, ex, r = self.evoluir(self.MUDA_ALU)
        self.assertTrue(r.objetivo_atingido)
        escritas = [(a, p) for f, a, p in modelo.pedidos if f == "escrita"]
        self.assertEqual([a for a, _ in escritas], ["src/alu.vhd"])
        self.assertIn("APPROVED for the previous specification", escritas[0][1])
        for nome in ("regs", "cpu"):
            self.assertEqual((pasta / "src" / f"{nome}.vhd").read_text(encoding="utf-8"),
                             (origem / "src" / f"{nome}.vhd").read_text(encoding="utf-8"))
        self.assertEqual([a for f, a, _ in modelo.pedidos if f == "testbench"], ["alu"])
        self.assertTrue((r.sessao / "testes_casos" / "alu" / "publicos" / "anterior-test_alu.py").exists())
        self.assertEqual(ex.chamadas[-1]["etapa"], "rv32im")
        resultado = json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))
        self.assertEqual(resultado["evolucao"]["mudaram"], ["alu"])
        self.assertEqual(resultado["evolucao"]["congelados"], ["cpu", "regs"])
        plano_md = (r.sessao / "evolucao" / "plano.md").read_text(encoding="utf-8")
        self.assertIn("RV32M adds mul/div", plano_md)
        self.assertIn("| `regs` | mantido (congelado) |", plano_md)
        arq = json.loads((pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual(arq["isa"], "rv32im")
        self.assertIn("mul", [i["mnemonic"] for i in arq["instructions"]])
        inicio = json.loads((r.sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual((inicio["modo"], inicio["isa_anterior"]), ("evoluir", "rv32i"))

    def test_bloco_novo_e_o_topo_que_o_instancia(self):
        _, pasta, modelo, _, r = self.evoluir(
            plano("separate M unit", MANTER("alu"), MANTER("regs"),
                  {"name": "muldiv", "action": "new", "responsibility": "RV32M ops",
                   "ports": ["a : in std_logic_vector(31 downto 0)"]},
                  {"name": "cpu", "action": "change", "change": "instantiate muldiv",
                   "depends_on": ["alu", "regs", "muldiv"]}),
            escritas=[vhdl("muldiv"), topo("alu", "regs", "muldiv")])
        self.assertTrue(r.objetivo_atingido)
        arq = json.loads((pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual([b["name"] for b in arq["blocks"]][-1], "cpu")
        self.assertIn("muldiv", arq["blocks"][-1]["depends_on"])
        self.assertEqual(sorted(a for f, a, _ in modelo.pedidos if f == "escrita"),
                         ["src/cpu.vhd", "src/muldiv.vhd"])

    def test_juntar_e_renomear_retira_os_blocos_antigos(self):
        _, pasta, modelo, _, r = self.evoluir(
            plano("merge alu and regs into one datapath",
                  {"name": "datapath", "action": "change", "from": ["alu", "regs"],
                   "change": "merge and add M", "responsibility": "ALU, M and registers",
                   "ports": ["a : in std_logic_vector(31 downto 0)"]},
                  {"name": "cpu", "action": "change", "change": "instantiate datapath",
                   "depends_on": ["datapath"]}),
            escritas=[vhdl("datapath"), topo("datapath")])
        self.assertTrue(r.objetivo_atingido)
        self.assertEqual(sorted(p.name for p in (pasta / "src").glob("*.vhd")),
                         ["cpu.vhd", "datapath.vhd"])
        escrita_datapath = next(p for f, a, p in modelo.pedidos
                                if f == "escrita" and a == "src/datapath.vhd")
        self.assertIn("-- previous alu.vhd", escrita_datapath)
        self.assertIn("-- previous regs.vhd", escrita_datapath)
        contrato = next(p for f, a, p in modelo.pedidos
                        if f == "revisao_especificacao" and a == "datapath")
        self.assertIn("### alu", contrato)
        self.assertIn("### regs", contrato)
        # os antigos ficam guardados na sessão, fora da CPU
        self.assertTrue((r.sessao / "evolucao" / "removidos" / "alu" / "alu.vhd").exists())
        resultado = json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))
        self.assertEqual(resultado["evolucao"]["blocos"]["datapath"]["de"], ["alu", "regs"])

    def test_sem_sessao_aprovada_e_erro_claro(self):
        vazio = self.raiz / "nada"
        (vazio / ".rvgen" / "sessao-1").mkdir(parents=True)
        with self.assertRaisesRegex(ErroGeracao, "não tem sessão aprovada"):
            evo.sessao_aprovada(vazio)


class TestTopoSemConta(unittest.TestCase):
    """Rodada real (06/11/2026): a evolução pôs MUL/DIV/REM inteiros no `cpu`."""

    def test_operacoes_aritmeticas_no_topo(self):
        self.assertEqual(operacoes_aritmeticas_no_topo(
            "r <= std_logic_vector(signed(a) * signed(b));\nq <= a / b;\nm <= a rem b;"),
            ["`*`", "`/`", "`rem`"])
        # comentário, `/=` e `**` não contam
        self.assertEqual(operacoes_aritmeticas_no_topo(
            "x <= a when b /= c else d; -- a*b / c rem d\n"), [])

    def test_com_a_regra_ligada_topo_com_conta_e_recusado(self):
        with tempfile.TemporaryDirectory() as d:
            agente = Agente(cliente=ModeloFalso(), executor=ExecutorFalso([]), pasta=Path(d),
                            microarquitetura="monociclo", isa="rv32im", relatar=lambda _: None,
                            protegidos=lambda: "selo", topo_sem_conta=True)
            arq = {"blocks": [{"name": "alu"}, {"name": "cpu"}]}
            ok_, motivo = agente._integracao_top_valida(
                "u_alu : entity work.alu port map ();\nm <= a * b;", arq)
            self.assertFalse(ok_)
            self.assertIn("never in the top", motivo)
            self.assertTrue(agente._integracao_top_valida(
                "u_alu : entity work.alu port map ();", arq)[0])
            self.assertIn("never allowed in `cpu`", agente._requisito_integracao_top(arq["blocks"]))

    def test_por_padrao_a_regra_esta_desligada(self):
        # pergunta do professor (06/11/2026): só liberar a decomposição já não
        # faria a IA criar o módulo novo? Fez (luna6_evolui_im_5); a regra
        # ficou como opção, desligada por padrão.
        with tempfile.TemporaryDirectory() as d:
            agente = Agente(cliente=ModeloFalso(), executor=ExecutorFalso([]), pasta=Path(d),
                            microarquitetura="monociclo", isa="rv32im", relatar=lambda _: None,
                            protegidos=lambda: "selo")
            arq = {"blocks": [{"name": "alu"}, {"name": "cpu"}]}
            self.assertTrue(agente._integracao_top_valida(
                "u_alu : entity work.alu port map ();\nm <= a * b;", arq)[0])
            self.assertNotIn("never allowed", agente._requisito_integracao_top(arq["blocks"]))
            self.assertIn("integration wiring", agente._requisito_integracao_top(arq["blocks"]))


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
        {"name": "regs", "file": "src/regs.vhd", "responsibility": "regs", "ports": ["w : in bit"],
         "depends_on": []},
        {"name": "cpu", "file": "src/cpu.vhd", "responsibility": "top", "ports": ["clk : in bit"],
         "depends_on": ["alu", "regs"]}]}

    def aplicar(self, *blocos, max_blocos=8):
        return evo.aplicar_plano(self.ARQ, {"understanding": "", "blocks": list(blocos)}, max_blocos)

    def test_dividir_um_bloco_em_dois(self):
        arq, acoes, removidos, motivo = self.aplicar(
            {"name": "adder", "action": "change", "from": ["alu"], "responsibility": "add",
             "ports": ["a : in bit"]},
            {"name": "shifter", "action": "change", "from": ["alu"], "responsibility": "shift",
             "ports": ["a : in bit"]},
            MANTER("regs"),
            {"name": "cpu", "action": "change", "depends_on": ["adder", "shifter", "regs"]})
        self.assertEqual(motivo, "")
        self.assertEqual(removidos, [])     # alu vira origem de dois blocos, não some sem rastro
        self.assertEqual(acoes["adder"]["de"], ["alu"])
        self.assertEqual([b["name"] for b in arq["blocks"]], ["adder", "shifter", "regs", "cpu"])

    def test_remover_um_bloco(self):
        arq, _, removidos, motivo = self.aplicar(
            {"name": "alu", "action": "change", "change": "absorbs regs"},
            {"name": "cpu", "action": "change", "depends_on": ["alu"]})
        self.assertEqual((motivo, removidos), ("", ["regs"]))

    def test_topo_precisa_mudar_quando_a_decomposicao_muda(self):
        motivo = self.aplicar(MANTER("alu"), MANTER("regs"),
                              {"name": "muldiv", "action": "new", "responsibility": "m", "ports": []},
                              MANTER("cpu"))[3]
        self.assertIn("precisa ser change", motivo)

    def test_portas_num_texto_so_tambem_valem(self):
        # rodada real (06/11/2026): a IA mandou `ports` como "a; b" e o plano,
        # idêntico ao original, foi recusado como se mudasse as portas
        arq, _, _, motivo = self.aplicar(
            {"name": "alu", "action": "keep", "ports": "a : in   bit"},
            {"name": "regs", "action": "change", "ports": "w : in bit; x : out bit"},
            MANTER("cpu"))
        self.assertEqual(motivo, "")
        self.assertEqual(arq["blocks"][1]["ports"], ["w : in bit", "x : out bit"])

    def test_portas_do_topo_sao_do_contrato(self):
        arq, _, _, motivo = self.aplicar(
            {"name": "alu", "action": "change"}, MANTER("regs"),
            {"name": "cpu", "action": "change", "ports": ["z : in bit"]})
        self.assertEqual(motivo, "")
        self.assertEqual(arq["blocks"][-1]["ports"], ["clk : in bit"])

    def test_limite_de_blocos_e_parametro(self):
        blocos = [{"name": f"b{i}", "action": "new", "responsibility": "x", "ports": []}
                  for i in range(9)]
        cpu = {"name": "cpu", "action": "change", "depends_on": [f"b{i}" for i in range(9)]}
        self.assertIn("de 2 a 8", self.aplicar(*blocos, cpu)[3])
        self.assertEqual(self.aplicar(*blocos, cpu, max_blocos=16)[3], "")

    def test_planos_invalidos(self):
        self.assertIn("keep, change ou new", self.aplicar({"name": "alu", "action": "x"})[3])
        self.assertIn("não existe", self.aplicar({"name": "fpu", "action": "keep"})[3])
        self.assertIn("inexistente", self.aplicar(
            {"name": "alu", "action": "change", "from": ["fpu"]}, MANTER("cpu"))[3])
        self.assertIn("não muda nenhum bloco", self.aplicar(
            MANTER("alu"), MANTER("regs"), MANTER("cpu"))[3])
        self.assertIn("falta o topo", self.aplicar({"name": "alu", "action": "change"})[3])
        self.assertIn("use change", self.aplicar(
            {"name": "alu", "action": "keep", "ports": ["b : in bit"]}, MANTER("cpu"))[3])


if __name__ == "__main__":
    unittest.main()
