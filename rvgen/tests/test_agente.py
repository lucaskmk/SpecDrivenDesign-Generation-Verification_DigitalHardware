#!/usr/bin/env python3
"""Testes do laco do agente, com modelo e executor falsos.

REQ: FR-RV-47 (entrega completa), FR-RV-48 (correcao guiada pelo
diagnostico, desfazendo o que piora), FR-RV-49 (veredito so da execucao
completa; escrita so em src/; arquivos protegidos), FR-RV-50 (sessao).

O modelo falso responde por fase, olhando o pedido; o executor falso devolve
relatorios no formato do `--json` do rvverify, em sequencia. Assim cada
caminho do laco e exercitado sem GHDL e sem Ollama -- rodar os dois de
verdade e o papel da TRV-9.8.
"""

from __future__ import annotations

import json
import re
import tempfile
import unittest
from pathlib import Path

from rvgen import contrato as ct
from rvgen.agente import (Agente, ErroGeracao, ErroIntegridade,
                             _falha_de_assertion, componentes_nao_integrados,
                             tabela_falhas_cocotb, validar_arquitetura)
from rvgen.executor import Execucao, Executor
from rvgen.llm import Resposta


def vhdl(nome: str, marca: str = "") -> str:
    instancias = ""
    if nome == "cpu":
        instancias = "\n".join(
            f"  u_{componente} : entity work.{componente} port map ();"
            for componente in ("decoder", "alu", "regs", "register_file", "branch_unit", "next_pc", "load_store_unit")) + "\n"
    return (f"```vhdl\n-- REQ: FR-RV-04\nentity {nome} is\nend {nome};\n"
              f"architecture rtl of {nome} is\nbegin\n{instancias}  -- {marca}\nend rtl;\n```")


def testbench() -> str:
    return ("```python\nimport cocotb\n\n@cocotb.test()\nasync def smoke(dut):\n"
            "    assert dut is not None\n```")


class ModeloFalso:
    """Responde por fase; `roteiro[fase]` e uma lista consumida em ordem."""

    provedor = "falso"
    modelo = "falso:1b"

    def __init__(self, roteiro: dict[str, list] | None = None) -> None:
        self.roteiro = roteiro or {}
        self.pedidos: list[tuple[str, str]] = []
        self.temperaturas: list[tuple[str, float | None]] = []
        self.schemas: list[tuple[str, dict | None]] = []

    def _fase(self, texto: str) -> tuple[str, str]:
        if "Document the CPU instructions before decomposition" in texto:
            return "instrucoes", "-"
        if "Define the complete semantic contract for component" in texto:
            m = re.search(r"component `([^`]+)`", texto)
            return "especificacao_componente", m.group(1) if m else "-"
        if "Review the semantic contract for component" in texto:
            m = re.search(r"component `([^`]+)`", texto)
            return "revisao_especificacao", m.group(1) if m else "-"
        if "Act as an independent semantic reviewer" in texto:
            m = re.search(r"component `([^`]+)`", texto)
            return "revisao_semantica_especificacao", m.group(1) if m else "-"
        if "Act as an independent convergence reviewer" in texto:
            m = re.search(r"component `([^`]+)`", texto)
            return "revisao_convergencia_componente", m.group(1) if m else "-"
        if "Decompose this" in texto:
            return "decomposicao", "-"
        if m := re.search(r"Which ONE file", texto):
            return "escolha", "-"
        if m := re.search(r"^Fix (src/\w+\.vhd)", texto, re.MULTILINE):
            return "correcao", m.group(1)
        if "Classify this component-test failure" in texto:
            return "triagem_componente", "-"
        if "independent, MINIMAL Cocotb diagnostic testbench" in texto:
            return "diagnostico_componente", "-"
        if "Act as an internal diagnostic planner" in texto:
            return "diagnostico_interno_componente", "-"
        if "Fix ONLY this complete Cocotb Python testbench" in texto:
            return "correcao_testbench", "-"
        if "Write a MINIMAL Cocotb smoke test" in texto or "Cocotb regression module" in texto:
            m = re.search(r"entity `([^`]+)`", texto)
            return "testbench", m.group(1) if m else "-"
        if "Expand this already passing Cocotb smoke test" in texto:
            return "ampliacao_testbench", "-"
        if "ONE new, standalone Cocotb module" in texto:
            return "caso_publico_isolado", "-"
        if "ONE new, standalone INTERNAL Cocotb diagnostic module" in texto:
            return "caso_interno_isolado", "-"
        if "Act as the evidence orchestrator for Cocotb suite" in texto:
            return "orquestracao_expansao_testbench", "-"
        m = re.search(r"Write the complete file (src/\w+\.vhd)", texto)
        return "escrita", m.group(1)

    def conversar(self, mensagens, *, schema=None, temperatura=None):
        # a fase se le no PRIMEIRO pedido: uma nova tentativa so acrescenta
        # "mande de novo" ao fim da conversa
        pedido = mensagens[1]["content"]
        fase, alvo = self._fase(pedido)
        self.pedidos.append((fase, alvo, pedido))
        self.temperaturas.append((fase, temperatura))
        self.schemas.append((fase, schema))
        fila = self.roteiro.get(fase)
        if fila:
            texto = fila.pop(0)
        elif fase == "escrita" or fase == "correcao":
            texto = vhdl(Path(alvo).stem, marca=f"{fase} {len(self.pedidos)}")
        elif fase in ("testbench", "correcao_testbench", "diagnostico_componente",
                       "caso_publico_isolado"):
            texto = testbench()
        elif fase == "ampliacao_testbench":
            texto = "COMPLETE"
        elif fase == "orquestracao_expansao_testbench":
            texto = "COMPLETE"
        elif fase == "diagnostico_interno_componente":
            texto = '{"probes": []}'
        elif fase in ("especificacao_componente", "revisao_especificacao"):
            texto = ("## Timing\ncombinational\n\n## Reset\nnone\n\n"
                     "## Behavior\ndefined by the responsibility\n\n"
                      "## Operations\nnone\n\n## Edge cases\nnone\n\n"
                      "## Test strategy\n- Verify the declared public relation.")
        elif fase == "revisao_semantica_especificacao":
            texto = "APPROVED"
        elif fase == "revisao_convergencia_componente":
            texto = "## Verdict\nvhdl\n\n## Evidence\n- DUT behavior disagrees with the contract.\n\n## Next action\n- Correct VHDL."
        elif fase == "triagem_componente":
            texto = '{"causa": "vhdl", "evidencias": ["assertion after DUT execution"]}'
        elif fase == "instrucoes":
            nomes = re.search(r"Document these mnemonics: (.+?)\.", pedido).group(1).split(", ")
            texto = json.dumps({"instructions": [
                {"mnemonic": nome, "description": f"implements {nome}"} for nome in nomes]})
        elif fase == "decomposicao":
            texto = "nao sei"
        else:
            texto = '{"file": "src/cpu.vhd", "reason": "?"}'
        return Resposta(texto, self.provedor, self.modelo, 10, 5, 0.1)


def relatorio(*, compilou=True, erros=(), casos=(), veredito=None, rv32i=None):
    """Um relatorio no formato do --json do rvverify."""
    lista = [{"id": i, "name": i.split("/")[-1], "passed": ok,
              "requirements": ["FR-RV-04"], "detail": "",
              "diagnostico": None if ok else
              {"tipo": tipo, "titulo": tipo, "resumo": f"falhou {i}",
               "divergencias": [], "dica": ""}}
             for i, ok, tipo in casos]
    if veredito is None:
        veredito = "aprovado" if lista and all(c["passed"] for c in lista) else "reprovado"
    return {"design": "x", "veredito": veredito,
            "compilacao": {"ok": compilou, "erros": list(erros)},
            "casos": lista, "por_etapa": {"rv32i": rv32i or {}}}


def ok(n=2, prefixo="rv32i"):
    return relatorio(casos=[(f"{prefixo}/c{k}", True, "") for k in range(n)])


class ExecutorFalso(Executor):
    nome = "falso"

    def __init__(self, relatorios: list[dict], componentes: list[dict] | None = None) -> None:
        super().__init__()
        self.relatorios = list(relatorios)
        self.chamadas: list[dict] = []
        self.componentes = list(componentes or [])

    def rodar(self, pasta, *, json_saida, workdir, build_root, casos=None,
              etapa="ambas", timeout=0, ondas=False, traco_completo=False):
        self.chamadas.append({"etapa": etapa, "casos": casos, "rotulo": json_saida.stem})
        rel = self.relatorios.pop(0)
        if isinstance(rel, tuple):          # (relatorio, texto do build.log)
            rel, log = rel
            (workdir / "gerada").mkdir(parents=True, exist_ok=True)
            (workdir / "gerada" / "build.log").write_text(log, encoding="utf-8")
        json_saida.parent.mkdir(parents=True, exist_ok=True)
        json_saida.write_text(json.dumps([rel]), encoding="utf-8")
        return Execucao(["rvverify"], 0 if rel["veredito"] == "aprovado" else 1,
                         rel, "", 1.0, json_saida)

    def rodar_componente(self, pasta, *, componente, teste, json_saida, workdir, build_root,
                          fontes=None, vcd=None, timeout=0):
        self.chamadas.append({"componente": componente, "teste": teste,
                               "fontes": fontes, "vcd": vcd, "rotulo": json_saida.stem})
        rel = self.componentes.pop(0)
        json_saida.parent.mkdir(parents=True, exist_ok=True)
        json_saida.write_text(json.dumps(rel), encoding="utf-8")
        return Execucao(["component_runner"], 0 if rel["passed"] else 1,
                         rel, "", 1.0, json_saida)


PLANO_VALIDO = json.dumps({"blocks": [
    {"name": "cpu", "responsibility": "top", "ports": [], "satisfies": ["FR-RV-05"],
     "design_rationale": "contract"},
    {"name": "alu", "responsibility": "alu", "ports": [], "satisfies": ["FR-RV-04"],
     "design_rationale": "area"},
    {"name": "regs", "responsibility": "register file", "ports": [],
     "satisfies": ["FR-RV-06"], "design_rationale": "vpi"}],
    "notes": "ok"})


class TestAgente(unittest.TestCase):

    def test_top_exige_instancia_entity_work_com_port_map_para_cada_bloco(self):
        blocos = [
            {"name": "decoder"}, {"name": "alu"}, {"name": "cpu"},
        ]
        fonte = """architecture rtl of cpu is
begin
  u_decoder : entity work.decoder port map (instr => instr_data);
end rtl;"""
        self.assertEqual(componentes_nao_integrados(fonte, blocos), ["alu"])
        fonte += "\n  u_alu : entity work.alu port map (op_a => x);"
        self.assertEqual(componentes_nao_integrados(fonte, blocos), [])

    def test_regressao_oficial_reproduzida_e_portao_antes_da_suite(self):
        componentes = [{"passed": False, "detail": "resultado ALU incorreto"}]
        ex = ExecutorFalso([], componentes)
        agente = self.agente(ModeloFalso(), ex)
        raiz = agente.sessao / "regressoes_oficiais"
        raiz.mkdir(parents=True)
        teste = raiz / "test_rv32ui_p_add.py"
        teste.write_text("import cocotb\n", encoding="utf-8")
        agente._log({"evento": "regressao_oficial_gerada", "teste_oficial": "rv32ui-p-add",
                     "arquivo": teste.relative_to(agente.pasta).as_posix(), "reproduziu": True})

        passou, evidencia = agente._validar_regressoes_oficiais(
            {"blocks": [{"name": "cpu"}]}, 3)

        self.assertFalse(passou)
        self.assertIn("rv32ui-p-add", evidencia)
        self.assertEqual(ex.chamadas[0]["rotulo"], "it03-focado-rv32ui_p_add")

    def test_escolha_de_defeito_recebe_todos_os_vhdls_e_linhas(self):
        modelo = ModeloFalso({"escolha": [
            '{"file": "src/alu.vhd", "reason": "opcode stale", "lines": [3]}'
        ]})
        agente = self.agente(modelo, ExecutorFalso([]))
        (self.pasta / "src").mkdir(parents=True)
        agente.sessao.mkdir(parents=True)
        (self.pasta / "src/cpu.vhd").write_text("-- CPU_SENTINEL\n", encoding="utf-8")
        (self.pasta / "src/alu.vhd").write_text("-- ALU_SENTINEL\n-- x\n-- bad\n", encoding="utf-8")
        arq = {"blocks": [
            {"name": "cpu", "file": "src/cpu.vhd", "responsibility": "top"},
            {"name": "alu", "file": "src/alu.vhd", "responsibility": "arithmetic"},
        ]}

        arquivo, diagnostico = agente._escolher("focal Cocotb failed", arq)

        self.assertEqual(arquivo, "src/alu.vhd")
        self.assertIn("cited lines: 3", diagnostico)
        pedido = modelo.pedidos[-1][2]
        self.assertIn("CPU_SENTINEL", pedido)
        self.assertIn("ALU_SENTINEL", pedido)
        schema = modelo.schemas[-1][1]
        self.assertIn("lines", schema["required"])

    def test_modulo_cocotb_exige_argumento_dut(self):
        invalido = ("import cocotb\n@cocotb.test()\nasync def caso():\n"
                    "    assert dut.x.value == 1\n")
        valido = ("import cocotb\n@cocotb.test()\nasync def caso(dut):\n"
                  "    assert dut.x.value == 1\n")
        self.assertFalse(Agente._modulo_cocotb_valido(invalido, um_teste=True))
        self.assertTrue(Agente._modulo_cocotb_valido(valido, um_teste=True))

    def test_modulo_cocotb_nao_exige_assert_estatico(self):
        codigo = ("import cocotb\n@cocotb.test()\nasync def caso(dut):\n"
                  "    dut.enable.value = 1\n")
        self.assertTrue(Agente._modulo_cocotb_valido(codigo, um_teste=True))
        self.assertTrue(Agente._smoke_cocotb_valido(codigo))

    def test_estimulo_rv32i_explica_instrucao_codificada_a_mao(self):
        agente = object.__new__(Agente)
        agente.isa = "rv32i"
        codigo = ("async def caso(dut):\n"
                  "    program = assemble_rv32i('lw x1, 0(x0)\\ndone: jal x0, done')\n"
                  "    dut.instr_data.value = 0x00000013\n"
                  "    dut.instr_data.value = program[0]\n")
        motivos = agente._motivos_estimulo_rv32i(
            codigo, {"caso"}, ["instr_data"], exigir_labels_controle=True)
        self.assertIn("hand_encoded_instruction", {m["kind"] for m in motivos})
        self.assertEqual(next(m for m in motivos if m["kind"] == "hand_encoded_instruction")["port"],
                         "instr_data")

    def test_foco_oficial_preserva_falha_materializada_mesmo_sem_reproducao(self):
        agente = object.__new__(Agente)
        agente._regressoes_oficiais_existentes = lambda: {"rv32ui-p-lhu", "rv32ui-p-ld_st"}
        ex = Execucao([], 1, {"results": [
            {"test": "rv32ui-p-lb", "status": "failed"},
            {"test": "rv32ui-p-lhu", "status": "failed"},
            {"test": "rv32ui-p-ld_st", "status": "failed"},
        ]}, "", 0.1, Path("r.json"))
        self.assertEqual(agente._proxima_regressao_oficial(ex), "rv32ui-p-lhu")

    def test_revisao_causal_normaliza_formato_descritivo_e_aceita_vpi_diagnostico(self):
        revisao = Agente._normalizar_revisao_hipotese({
            "semantic_validity": "invalid",
            "decision": "reject",
            "reason": "The experiment reads internal VPI signals and cannot approve conformance.",
            "waveform_observations": [
                {"time_ns": 20, "observation": "effective address is correct"},
                {"time_ns": 30, "observation": "store carries the loaded value"},
            ],
            "another_test_needed": True,
            "next_hypothesis": "check signed write-back",
            "recommended_discriminating_plan": "store 0xFFFFFF80 through public ports",
        })
        self.assertTrue(revisao["diagnostic_test_valid"])
        self.assertFalse(revisao["normative_approval_allowed"])
        self.assertEqual(revisao["verdict"], "inconclusive")
        self.assertEqual(len(revisao["evidence"]), 2)
        self.assertEqual(revisao["next_test_plan"],
                         "store 0xFFFFFF80 through public ports")

    def test_revisao_causal_normaliza_objetos_aninhados(self):
        revisao = Agente._normalizar_revisao_hipotese({
            "semantic_validity": {"verdict": "diagnostic-valid-only",
                                  "normative_approval": False,
                                  "reason": "VPI probe is diagnostic-only"},
            "hypothesis_assessment": {"verdict": "inconclusive",
                                        "reason": "stimulus never reached LB"},
            "concrete_observations": ["PC never reached the load", "no marker store occurred"],
            "vcd_decision": {"another_test_necessary": True},
            "next_hypothesis": "repair reachability fixture",
            "recommended_discriminating_plan": {
                "test": "run a reduced public-port fixture",
                "interpretation": "observe marker store",
            },
        })
        self.assertTrue(revisao["diagnostic_test_valid"])
        self.assertFalse(revisao["normative_approval_allowed"])
        self.assertEqual(revisao["verdict"], "inconclusive")
        self.assertTrue(revisao["next_test_needed"])
        self.assertEqual(revisao["next_test_plan"], "run a reduced public-port fixture")

    def test_orquestrador_escolhe_probes_internos_do_inventario(self):
        agente = object.__new__(Agente)
        agente.contrato_testes = ""
        agente.relatar = lambda _: None
        agente._chamar = lambda *_args, **_kwargs: Resposta(json.dumps({
            "id": "load_result", "hypothesis": "LB reaches load_result",
            "observation_paths": ["dut.valid_load", "dut.load_result"],
            "test_plan": "execute LB and observe its result",
            "failure_meaning": "load result differs from selected byte",
        }), "fake", "fake", 1, 1, 0.0)
        plano = agente._planejar_diagnostico_interno_cpu(
            {"ports": ["clk : in std_logic", "data_addr : out std_logic_vector"]},
            "rv32ui-p-lb", "official LB failure",
            ["dut.clk", "dut.data_addr", "dut.valid_load", "dut.load_result"],
            {"stages": {}})
        self.assertEqual(plano["id"], "load_result")
        self.assertEqual(plano["observation_paths"], ["dut.valid_load", "dut.load_result"])

    def test_estado_pendente_do_diagnostico_preserva_o_plano_e_os_sinais(self):
        plano = {"id": "register_commit", "hypothesis": "observe commit",
                 "observation_paths": ["dut.reg_write", "dut.load_result"],
                 "test_plan": "reach LB", "failure_meaning": "commit diverged"}
        estado = {"pending_testbench": {"plan": plano, "attempts": 1,
                                         "detail": "missing_internal_probe"}}
        self.assertEqual(estado["pending_testbench"]["plan"]["id"], "register_commit")
        self.assertEqual(estado["pending_testbench"]["plan"]["observation_paths"],
                         ["dut.reg_write", "dut.load_result"])

    def test_marcador_cocotb_detecta_avanco_temporal_ou_assertion_posterior(self):
        def execucao(texto, passou=False):
            rel = {"compilacao": {"ok": True}, "passed": passou, "diagnostico": texto}
            return Execucao([], 0 if passou else 1, rel, "", 0.1, Path("r.json"))

        primeiro = Agente._marcador_progresso_cocotb(execucao(
            ' 12.00ns WARNING test failed\n File "/x/test.py", line 40'))
        posterior = Agente._marcador_progresso_cocotb(execucao(
            ' 18.00ns WARNING test failed\n File "/x/test.py", line 55'))
        aprovado = Agente._marcador_progresso_cocotb(execucao("passed", True))
        self.assertGreater(posterior[1], primeiro[1])
        self.assertGreater(posterior[2], primeiro[2])
        self.assertGreater(aprovado[0], posterior[0])

    def test_hipotese_inferior_rejeitada_ativa_exploracao_cpu_por_hash(self):
        agente = self.agente(ModeloFalso(), ExecutorFalso([]))
        (self.pasta / "src").mkdir(parents=True)
        (self.pasta / "src" / "cpu.vhd").write_text("entity cpu is end;", encoding="utf-8")
        cpu = {"name": "cpu", "file": "src/cpu.vhd"}

        agente._bloquear_hipotese_focal("rv32ui-p-lhu", cpu, "src/load_store_unit.vhd", "passou")

        _, estado = agente._estado_exploracao_cpu("rv32ui-p-lhu", cpu)
        self.assertTrue(estado["ativado"])
        self.assertEqual(estado["bloqueados"]["src/load_store_unit.vhd"], "passou")

    def test_tabela_de_falhas_cocotb_reune_todos_os_testes(self):
        fonte = """import cocotb
@cocotb.test()
async def test_s(dut):
    dut.instr.value = 0x28
@cocotb.test()
async def test_b(dut):
    dut.instr.value = 0xFF8000F8
"""
        log = """running test_imm_gen.test_s (1/2)
test_imm_gen.test_s imm_s expected 0x00000005, got 0x00000000
test_imm_gen.test_s failed
running test_imm_gen.test_b (2/2)
test_imm_gen.test_b imm_b expected 0xFFFFFFFE, got 0xFFFFFFE0
test_imm_gen.test_b failed
"""
        tabela = tabela_falhas_cocotb(log, fonte)
        self.assertIn("corrija todas as linhas", tabela)
        self.assertIn("`test_s`", tabela)
        self.assertIn("`instr=0x28`", tabela)
        self.assertIn("esperado 0xFFFFFFFE, observado 0xFFFFFFE0", tabela)

    def test_falha_de_assertion_exige_compilacao_bem_sucedida(self):
        ex_assertion = Execucao([], 1, {"compilacao": {"ok": True},
                                        "diagnostico": "AssertionError: resultado incorreto"},
                               "", 0, Path("resultado.json"))
        ex_build = Execucao([], 1, {"compilacao": {"ok": False},
                                    "diagnostico": "AssertionError em texto antigo"},
                            "", 0, Path("resultado.json"))
        self.assertTrue(_falha_de_assertion(ex_assertion))
        self.assertFalse(_falha_de_assertion(ex_build))

    def test_falha_de_assertion_usa_excecao_final_nao_linha_assert(self):
        ex = Execucao([], 1, {"compilacao": {"ok": True}, "diagnostico": """
Traceback (most recent call last):
  File \"test.py\", line 12
    assert int(dut.write_data.value) == expected
AttributeError: cpu contains no child object named write_data
"""}, "", 0, Path("resultado.json"))
        self.assertFalse(_falha_de_assertion(ex))

        assertion = Execucao([], 1, {"compilacao": {"ok": True}, "diagnostico": """
Traceback (most recent call last):
  File \"test.py\", line 20
    assert observed == expected
AssertionError: expected 1, observed 0
"""}, "", 0, Path("resultado.json"))
        self.assertTrue(_falha_de_assertion(assertion))

    def test_sessao_reconhece_expansao_incremental_concluida(self):
        agente = self.agente(ModeloFalso(), ExecutorFalso([]))
        agente.sessao.mkdir(parents=True)
        (agente.sessao / "sessao.jsonl").write_text(
            '{"evento": "testbench_expansao_concluida", "bloco": "alu"}\n', encoding="utf-8")
        self.assertTrue(agente._expansao_testbench_concluida({"name": "alu"}))
        self.assertFalse(agente._expansao_testbench_concluida({"name": "regfile"}))

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "gerada"
        self.linhas: list[str] = []

    def tearDown(self):
        self._tmp.cleanup()

    def agente(self, modelo, executor, *, isa="rv32im", microarquitetura="monociclo",
               iteracoes=5, protegidos=None, **kw):
        return Agente(cliente=modelo, executor=executor, pasta=self.pasta,
                       microarquitetura=microarquitetura, isa=isa, iteracoes=iteracoes,
                      relatar=self.linhas.append,
                      protegidos=protegidos or (lambda: "selo"),
                      caso_de_fumaca=lambda: "rv32i/add", **kw)

    def test_caminho_feliz_rv32im_e_sessao_registrada(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([ok(1), ok(24), ok(35)])
        r = self.agente(modelo, ex).gerar()

        self.assertTrue(r.objetivo_atingido)
        self.assertEqual((r.veredito, r.iteracoes), ("aprovado", 0))
        # fumaca com 1 caso e suite oficial completa; a última é o veredito
        self.assertEqual([(c["etapa"], c["casos"]) for c in ex.chamadas],
                         [("rv32im", ["rv32i/add"]), ("rv32im", None)])
        # o top e escrito por ultimo, mesmo proposto primeiro pelo modelo
        escritos = [a for f, a, _ in modelo.pedidos if f == "escrita"]
        self.assertEqual(escritos, ["src/alu.vhd", "src/regs.vhd", "src/cpu.vhd"])
        arq = json.loads((self.pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual(arq["origem"], "modelo")
        self.assertNotIn("provided", arq)
        self.assertEqual(len(arq["instructions"]), len(ct.instrucoes_da_isa("rv32im")))
        self.assertTrue(all(i["description"] for i in arq["instructions"]))
        self.assertFalse((self.pasta / "cpu.toml").exists())

        eventos = [json.loads(l) for l in
                   (r.sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines()]
        llm = [e for e in eventos if e["evento"] == "llm"]
        self.assertEqual(llm[0]["mensagens"][0], {"role": "system", "content": "@contrato.txt"})
        self.assertTrue((r.sessao / "contrato.txt").read_text(encoding="utf-8").startswith("You write VHDL"))
        self.assertTrue((r.sessao / "testes.md").exists())
        resultado = json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))
        self.assertEqual((resultado["veredito"], resultado["modelo"]), ("aprovado", "falso:1b"))

    def test_tela_mostra_as_fases_em_ordem(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        self.agente(modelo, ExecutorFalso([ok(1), ok(24), ok(35)])).gerar()
        fases = [l.split("]")[0] + "]" for l in self.linhas if l.startswith("[")]
        self.assertEqual(fases, ["[1/4]", "[2/4]", "[2/4]", "[2/4]", "[2/4]", "[3/4]", "[4/4]"])
        self.assertIn("[2/4] escrevendo src/alu.vhd (arquivo 1 de 3) ...", self.linhas)
        self.assertIn("  fluxo: ● Arquitetura ──▶ ○ Componentes ──▶ ○ spec-riscv-test ──▶ ○ Veredito",
                       self.linhas)
        self.assertIn("  spec-riscv-test fumaca: fumaca oficial (rv32i/add) ...", self.linhas)
        self.assertIn("  spec-riscv-test suite: suite oficial RV32IM ...", self.linhas)
        self.assertTrue(any("CPU: RV32IM, microarquitetura monociclo" in l for l in self.linhas))

    def test_contratos_de_todos_os_blocos_precedem_a_primeira_escrita_vhdl(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        componentes = [{"compilacao": {"ok": True}, "passed": True, "detail": "ok"}] * 6
        self.agente(modelo, ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], componentes),
                    testes_componentes=True, gates_componentes=True).gerar()
        fases = [fase for fase, _, _ in modelo.pedidos]
        primeira_escrita = fases.index("escrita")
        self.assertEqual(fases[:primeira_escrita].count("especificacao_componente"), 3)
        self.assertEqual(fases[:primeira_escrita].count("revisao_semantica_especificacao"), 3)

    def test_testes_de_componentes_geram_um_por_vhdl_antes_do_rvverify(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        componentes = [{"compilacao": {"ok": True}, "passed": True, "detail": "ok"}] * 6
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], componentes)
        r = self.agente(modelo, ex, testes_componentes=True).gerar()
        self.assertTrue(r.objetivo_atingido)
        self.assertEqual([c["componente"] for c in ex.chamadas if "componente" in c],
                         ["alu", "regs", "cpu", "cpu"])
        self.assertEqual(len([p for f, _, p in modelo.pedidos if f == "testbench"]), 3)
        self.assertEqual(len([p for f, _, p in modelo.pedidos
                              if f == "orquestracao_expansao_testbench"]), 3)
        self.assertEqual(len([p for f, _, p in modelo.pedidos
                              if f == "especificacao_componente"]), 3)
        self.assertEqual(len([p for f, _, p in modelo.pedidos
                              if f == "revisao_semantica_especificacao"]), 3)
        prompt_smoke = next(p for f, _, p in modelo.pedidos if f == "testbench")
        self.assertIn("Public DUT interface", prompt_smoke)
        self.assertIn("Normative component semantic contract", prompt_smoke)
        self.assertNotIn("architecture rtl", prompt_smoke)
        prompt_orquestracao = next(p for f, _, p in modelo.pedidos
                                   if f == "orquestracao_expansao_testbench")
        self.assertIn("Compare the CURRENT passing suite", prompt_orquestracao)
        self.assertIn("Coverage budget: 0 incremental case(s) already approved; the hard limit is 32",
                      prompt_orquestracao)
        self.assertIn("MUST NOT exceed the available budget (32)", prompt_orquestracao)
        self.assertIn("do NOT select reserved, illegal, unallocated, or malformed", prompt_orquestracao)
        self.assertTrue((r.sessao / "component_specs" / "alu.comp_spec.txt").exists())

    def test_orcamento_de_expansao_aprovado_nao_bloqueia_componente(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        componentes = [{"compilacao": {"ok": True}, "passed": True, "detail": "ok"}] * 6
        r = self.agente(modelo, ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], componentes),
                        testes_componentes=True, max_casos_teste=0).gerar()
        self.assertTrue(r.objetivo_atingido)
        eventos = (r.sessao / "sessao.jsonl").read_text(encoding="utf-8")
        self.assertIn('"evento": "testbench_expansao_concluida"', eventos)
        self.assertIn('"motivo": "orcamento"', eventos)
        self.assertTrue(any("ORÇAMENTO" in linha for linha in self.linhas))
        self.assertTrue((r.sessao / "testes" / "test_alu.py").exists())
        eventos = [json.loads(l) for l in (r.sessao / "sessao.jsonl").read_text().splitlines()]
        chamada_teste = next(e for e in eventos if e.get("evento") == "llm" and e["fase"] == "testbench")
        self.assertEqual(chamada_teste["mensagens"][0]["content"], "@contrato-testes.txt")

    def test_portoes_aprovam_cada_bloco_antes_do_proximo(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        componentes = [{"compilacao": {"ok": True}, "passed": True, "detail": "ok"}] * 6
        ex = ExecutorFalso([ok(1), ok(24), ok(35)], componentes)
        r = self.agente(modelo, ex, testes_componentes=True, gates_componentes=True).gerar()
        escritos = [a for f, a, _ in modelo.pedidos if f == "escrita"]
        chamadas = [c for c in ex.chamadas if "componente" in c]
        self.assertEqual(escritos, ["src/alu.vhd", "src/regs.vhd", "src/cpu.vhd"])
        self.assertEqual([c["componente"] for c in chamadas],
                         ["alu", "regs", "cpu", "cpu"])
        self.assertTrue(all(c["fontes"] for c in chamadas))
        self.assertTrue((r.sessao / "componentes_aprovados" / "alu.json").exists())

    def test_falha_de_componente_vira_regressao_apos_a_correcao(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        falhou = {"compilacao": {"ok": True}, "passed": False, "detail": "SRA esperado -1"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        # smoke da alu falha; apos correcao, smoke, ampliacao e regressao passam;
        # os dois estagios dos demais componentes tambem passam.
        componentes = [falhou] + [passou] * 7
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], componentes)
        r = self.agente(modelo, ex, testes_componentes=True,
                        regressoes_componentes=True).gerar()
        self.assertTrue(r.objetivo_atingido)
        regressoes = list((r.sessao / "regressoes").glob("test_alu_regressao_*.py"))
        self.assertEqual(len(regressoes), 1)
        eventos = (r.sessao / "sessao.jsonl").read_text(encoding="utf-8")
        self.assertIn('"evento": "regressao_gerada"', eventos)

    def test_valor_fora_da_largura_contratada_corrige_testbench_nao_vhdl(self):
        plano = json.dumps({"blocks": [
            {"name": "cpu", "responsibility": "top", "ports": [],
             "satisfies": ["FR-RV-05"], "design_rationale": "contract"},
            {"name": "register_file", "responsibility": "regs",
             "ports": ["rd_data : in std_logic_vector(31 downto 0)"],
             "satisfies": ["FR-RV-04"], "design_rationale": "area"},
        ]})
        modelo = ModeloFalso({"decomposicao": [plano]})
        fora_da_largura = {
            "compilacao": {"ok": True}, "passed": False, "detail": "SystemExit: 1",
            "diagnostico": "ValueError: Int value (5726623060) out of range for assignment "
                           "of 32-bit signal ('rd_data')\nTraceback test_register_file.py",
        }
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], [fora_da_largura] + [passou] * 4)
        self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("triagem_componente", fases)
        self.assertIn("correcao_testbench", fases)
        self.assertNotIn("correcao", fases)

    def test_conversao_com_base_no_cocotb_corrige_testbench_nao_vhdl(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO],
                              "triagem_componente": [
                                  '{"causa":"ambigua","evidencias":["metavalor"]}']})
        falhou = {"compilacao": {"ok": True}, "passed": False,
                   "detail": "TypeError: int() can't convert non-string with explicit base"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)],
                             [falhou] + [passou] * 6)
        self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("correcao_testbench", fases)
        self.assertNotIn("correcao", fases)

    def test_coroutine_cocotb_sem_dut_corrige_testbench_nao_vhdl(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        falhou = {"compilacao": {"ok": True}, "passed": False,
                   "detail": "TypeError: test_alu_add() takes 0 positional arguments but 1 was given"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], [falhou] + [passou] * 7)
        self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("correcao_testbench", fases)
        self.assertNotIn("diagnostico_componente", fases)
        self.assertNotIn("correcao", fases)

    def test_ambiguidade_usa_diagnostico_antes_de_corrigir_o_teste(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO],
                              "triagem_componente": [
                                  '{"causa":"ambigua","evidencias":["sem conclusao"]}']})
        falhou = {"compilacao": {"ok": True}, "passed": False, "detail": "assertion falhou"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)],
                            [falhou] + [passou] * 7)
        r = self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("diagnostico_componente", fases)
        self.assertNotIn("correcao_testbench", fases)
        eventos = (r.sessao / "sessao.jsonl").read_text()
        self.assertIn('"evento": "diagnostico_componente"', eventos)
        self.assertIn('"evento": "diagnostico_promovido_a_smoke"', eventos)

    def test_triagem_spec_revisa_contrato_e_regera_o_componente(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO],
                               "triagem_componente": [
                                   '{"causa":"spec","evidencias":["opcode indefinido"]}']})
        falhou = {"compilacao": {"ok": True}, "passed": False, "detail": "assertion failed"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], [falhou] + [passou] * 7)
        r = self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("revisao_especificacao", fases)
        self.assertGreaterEqual(fases.count("escrita"), 4)
        eventos = (r.sessao / "sessao.jsonl").read_text()
        self.assertIn('"evento": "especificacao_revisada"', eventos)
        self.assertIn('"evento": "dependentes_spec_invalidados"', eventos)

    def test_revisor_semantico_revisa_spec_antes_do_vhdl(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO],
                               "revisao_semantica_especificacao": [
                                   "REVISE\n- selector mapping contradicts the ISA reference"]})
        self.agente(modelo, ExecutorFalso([ok(1), ok(24), ok(35)])).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("revisao_especificacao", fases)
        self.assertGreaterEqual(fases.count("revisao_semantica_especificacao"), 2)

    def test_corpo_da_spec_descarta_cabecalho_e_preserva_estrategia(self):
        completo = """# Component semantic contract: alu

## Public interface
```vhdl
entity alu is end alu;
```

## Responsibility
ALU.

## Timing
combinational

## Reset
none

## Behavior
adds

## Operations
- add

## Edge cases
- wrap

## Test strategy
- stale copy
"""
        corpo = Agente._corpo_especificacao_markdown(completo)
        self.assertTrue(corpo.startswith("## Timing"))
        self.assertNotIn("## Public interface", corpo)
        self.assertIn("## Test strategy", corpo)

    def test_corpo_da_spec_normaliza_titulos_equivalentes_do_revisor(self):
        texto = """## Public interface
fixed

## Responsibility and timing
Combinational transform.

## Operation encoding
ADD is selector zero.

## Edge cases
Wraparound.

## Test strategy
Observe selector zero.
"""
        corpo = Agente._corpo_especificacao_markdown(texto)
        for secao in ("Timing", "Reset", "Behavior", "Operations", "Edge cases", "Test strategy"):
            self.assertIn(f"## {secao}", corpo)
        self.assertIn("## Reset\nnone", corpo)

    def test_revisao_de_spec_retem_secoes_inalteradas_omitidas_pelo_modelo(self):
        anterior = """## Timing
old timing

## Reset
old reset

## Behavior
old behavior

## Operations
old operations

## Edge cases
old edges

## Test strategy
old strategy
"""
        revisao = """## Timing
new timing

## Reset
new reset

## Behavior
new behavior

## Test strategy
new strategy
"""
        corpo, preservadas = Agente._completar_revisao_de_spec(revisao, anterior)
        self.assertEqual(preservadas, ("Operations", "Edge cases"))
        self.assertIn("## Operations\nold operations", corpo)
        self.assertIn("## Edge cases\nold edges", corpo)
        self.assertIn("## Behavior\nnew behavior", corpo)

    def test_falhas_corretivas_repetidas_escalam_para_revisor_de_convergencia(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        falhou = {"compilacao": {"ok": True}, "passed": False, "detail": "assertion failed"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], [falhou, falhou] + [passou] * 6)
        r = self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("revisao_convergencia_componente", fases)
        eventos = (r.sessao / "sessao.jsonl").read_text()
        self.assertIn('"evento": "revisao_convergencia_componente"', eventos)

    def test_revisor_mixed_nao_reescreve_especificacao_normativa(self):
        modelo = ModeloFalso({
            "decomposicao": [PLANO_VALIDO],
            "revisao_convergencia_componente": [
                "## Verdict\nmixed\n\n## Evidence\n- evidence conflicts.\n\n"
                "## Next action\n- recover implementation."],
        })
        falhou = {"compilacao": {"ok": True}, "passed": False, "detail": "assertion failed"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)], [falhou, falhou] + [passou] * 6)
        self.agente(modelo, ex, testes_componentes=True).gerar()
        fases = [f for f, _, _ in modelo.pedidos]
        self.assertIn("revisao_convergencia_componente", fases)
        self.assertNotIn("revisao_especificacao", fases)

    def test_triagem_com_string_de_evidencia_nao_a_separa_em_caracteres(self):
        modelo = ModeloFalso({
            "decomposicao": [PLANO_VALIDO],
            "triagem_componente": ['{"causa":"vhdl","evidencias":"O reset falhou."}'],
        })
        falhou = {"compilacao": {"ok": True}, "passed": False, "detail": "assertion failed"}
        passou = {"compilacao": {"ok": True}, "passed": True, "detail": "ok"}
        ex = ExecutorFalso([ok(1), ok(1), ok(24), ok(35)],
                            [falhou] + [passou] * 6)
        r = self.agente(modelo, ex, testes_componentes=True).gerar()
        eventos = [json.loads(l) for l in (r.sessao / "sessao.jsonl").read_text().splitlines()]
        triagem = next(e for e in eventos if e["evento"] == "triagem_componente")
        self.assertEqual(triagem["evidencias"], ["O reset falhou."])

    def test_resumo_do_plano_incremental_indica_fator_e_estimulo(self):
        plano = ("Behavior: decode J-format immediate\n"
                 "New factor: negative sign extension\n"
                 "Stimulus: a negative JAL offset\n")
        resumo = Agente._resumo_plano_incremental(plano)
        self.assertIn("decode J-format immediate", resumo)
        self.assertIn("fator: negative sign extension", resumo)
        self.assertIn("estímulo: a negative JAL offset", resumo)

    def test_fontes_de_testes_preservam_decorador_e_corpo_executavel(self):
        codigo = ("import cocotb\n\n@cocotb.test()\nasync def caso(dut):\n"
                  "    assert dut is not None\n")
        fontes = Agente._fontes_testes_cocotb(codigo)
        self.assertEqual(list(fontes), ["caso"])
        self.assertTrue(fontes["caso"].startswith("@cocotb.test()"))
        self.assertIn("async def caso", fontes["caso"])

    def test_estimativa_aparece_a_partir_da_segunda_iteracao(self):
        falha = relatorio(casos=[("rv32i/c0", False, "valor"), ("rv32i/c1", True, "")])
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        # fumaca, etapa RV32I, uma execucao por iteracao (3) e o veredito final
        ex = ExecutorFalso([ok(1), falha, falha, falha, falha,
                            relatorio(casos=[("rv32i/c0", False, "valor")])])
        self.agente(modelo, ex, iteracoes=3).gerar()
        estimativas = [l for l in self.linhas if "rodadas restantes" in l]
        self.assertEqual(len(estimativas), 2)                 # antes da 2a e da 3a
        self.assertIn("se usar as 2 rodadas restantes", estimativas[0])

    def test_decomposicao_invalida_interrompe_sem_fallback(self):
        modelo = ModeloFalso({"decomposicao": ['{"blocks": []}', "texto sem json"]})
        with self.assertRaisesRegex(ErroGeracao, "decomposicao valida"):
            self.agente(modelo, ExecutorFalso([])).gerar()
        self.assertFalse((self.pasta / "architecture.json").exists())

    def test_prompt_de_decomposicao_nao_pede_ids_fr_rv(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        self.agente(modelo, ExecutorFalso([ok(1), ok(24), ok(35)])).gerar()
        pedido = next(p for fase, _, p in modelo.pedidos if fase == "decomposicao")
        self.assertIn("do NOT emit a `satisfies`", pedido)
        self.assertNotIn("`satisfies` lists requirement IDs", pedido)

    def test_erro_de_compilacao_corrige_o_arquivo_que_o_ghdl_apontou(self):
        erro = {"arquivo": "/job/entregas/gerada/src/alu.vhd", "linha": 12,
                "coluna": 5, "mensagem": "no declaration for \"foo\""}
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([relatorio(compilou=False, erros=[erro],
                                      casos=[("rv32i/add", False, "compilacao")]),
                            ok(1), ok(24), ok(35)])
        r = self.agente(modelo, ex).gerar()
        self.assertTrue(r.objetivo_atingido)
        self.assertEqual(r.iteracoes, 1)
        correcoes = [(a, p) for f, a, p in modelo.pedidos if f == "correcao"]
        self.assertEqual([a for a, _ in correcoes], ["src/alu.vhd"])
        self.assertIn("alu.vhd:12:5: no declaration", correcoes[0][1])
        self.assertNotIn("escolha", [f for f, _, _ in modelo.pedidos])
        self.assertIn("correcao", (self.pasta / "src" / "alu.vhd").read_text(encoding="utf-8"))

    def test_relatorio_sem_os_erros_le_o_build_log_e_mostra_a_linha(self):
        # o que o rvverify mandou de verdade na TRV-9.8, antes da correcao do
        # builder: a falha do `ghdl -m` virou "manifesto", sem erro nenhum
        manifesto = relatorio(compilou=None, casos=[("-/manifesto", False, "manifesto")])
        log = ("/job/entregas/gerada/src/alu.vhd:3:10: no declaration for \"x\"\n"
               "   y <= x;\n         ^\n"
               "/usr/lib/ghdl/ieee/v08/numeric_std-body.vhdl:1:1: aviso da IEEE\n")
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([(manifesto, log), ok(1), ok(24), ok(35)])
        self.agente(modelo, ex).gerar()
        correcoes = [(a, p) for f, a, p in modelo.pedidos if f == "correcao"]
        self.assertEqual([a for a, _ in correcoes], ["src/alu.vhd"])     # nao o top
        self.assertIn('alu.vhd:3:10: no declaration for "x"', correcoes[0][1])
        self.assertNotIn("numeric_std", correcoes[0][1])
        self.assertNotIn("escolha", [f for f, _, _ in modelo.pedidos])

    def test_erro_de_compilacao_vem_com_a_linha_do_fonte(self):
        erro = {"arquivo": "alu.vhd", "linha": 3, "coluna": 1, "mensagem": "erro aqui"}
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([relatorio(compilou=False, erros=[erro],
                                      casos=[("rv32i/add", False, "compilacao")]),
                            ok(1), ok(24), ok(35)])
        self.agente(modelo, ex).gerar()
        pedido = next(p for f, a, p in modelo.pedidos if f == "correcao")
        # a linha 3 do alu.vhd gerado pelo modelo falso e "end alu;"
        self.assertIn("alu.vhd:3:1: erro aqui\n    end alu;", pedido)

    def test_resposta_repetida_sobe_a_temperatura_ate_mudar(self):
        # TRV-9.8: com temperatura 0,2 o modelo devolveu o mesmo arquivo 10 vezes
        erro = {"arquivo": "alu.vhd", "linha": 2, "coluna": 1, "mensagem": "erro"}
        alu = vhdl("alu", "versao original")
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO],
                              "escrita": [alu],
                              "correcao": [alu, alu, vhdl("alu", "versao nova")]})
        ex = ExecutorFalso([relatorio(compilou=False, erros=[erro],
                                      casos=[("rv32i/add", False, "compilacao")]),
                            ok(1), ok(24), ok(35)])
        r = self.agente(modelo, ex).gerar()
        self.assertTrue(r.objetivo_atingido)
        # 0,2 repetiu -> 0,9; repetiu de novo -> continua 0,9; mudou
        self.assertEqual([t for f, t in modelo.temperaturas if f == "correcao"],
                         [None, 0.9, 0.9])
        self.assertTrue(any("temperatura 0.9" in l for l in self.linhas))
        self.assertIn("versao nova", (self.pasta / "src" / "alu.vhd").read_text(encoding="utf-8"))

    def test_mudar_sem_melhorar_mantem_a_temperatura_alta(self):
        # TRV-9.12: so uma MELHORA do placar devolve a temperatura normal
        erro = {"arquivo": "alu.vhd", "linha": 2, "coluna": 1, "mensagem": "erro"}
        nao_compila = relatorio(compilou=False, erros=[erro],
                                casos=[("rv32i/add", False, "compilacao")])
        alu = vhdl("alu", "original")
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO], "escrita": [alu],
                              "correcao": [alu, vhdl("alu", "a"), vhdl("alu", "b")]})
        # original repete; "a" muda mas nao compila (igual); "b" compila (melhora)
        ex = ExecutorFalso([nao_compila, nao_compila, ok(1),
                            relatorio(casos=[("rv32i/c0", False, "valor")]), ok(24), ok(35)])
        self.agente(modelo, ex).gerar()
        self.assertEqual([t for f, t in modelo.temperaturas if f == "correcao"],
                         [None, 0.9, 0.9, None])

    def test_descricao_vai_nos_pedidos_e_fica_registrada(self):
        descricao = "Register file with synchronous reset.\nSeparate decoder block."
        plano = json.loads(PLANO_VALIDO)
        plano["requests"] = [{"request": "synchronous reset", "blocks": ["regs"],
                              "how": "reset inside the clocked process"},
                             {"request": "", "blocks": [], "how": "vazio: descartado"}]
        erro = {"arquivo": "alu.vhd", "linha": 2, "coluna": 1, "mensagem": "erro"}
        modelo = ModeloFalso({"decomposicao": [json.dumps(plano)]})
        ex = ExecutorFalso([relatorio(compilou=False, erros=[erro],
                                      casos=[("rv32i/add", False, "compilacao")]),
                            ok(1), ok(24), ok(35)])
        r = self.agente(modelo, ex, descricao=f"  {descricao}  ").gerar()

        # nas tres classes de pedido, com o contrato por cima
        for fase in ("decomposicao", "escrita", "correcao"):
            pedido = next(p for f, a, p in modelo.pedidos if f == fase)
            self.assertIn(f"# Designer's description of the CPU (free text from the user)\n"
                          f"{descricao}\n", pedido, fase)
            self.assertIn("the contract wins", pedido)
        decomp = next(p for f, a, p in modelo.pedidos if f == "decomposicao")
        self.assertIn("Also answer `requests`", decomp)
        schema = next(s for f, s in modelo.schemas if f == "decomposicao")
        self.assertIn("requests", schema["required"])
        # rastreabilidade (declaracao do modelo) e registro
        arq = json.loads((self.pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual(arq["descricao"], descricao)
        self.assertEqual(arq["requests"], [{"request": "synchronous reset", "blocks": ["regs"],
                                            "how": "reset inside the clocked process"}])
        self.assertIn("NOT verified", arq["requests_note"])
        md = (self.pasta / "descricao.md").read_text(encoding="utf-8")
        self.assertIn("NAO verificado", md)
        self.assertTrue(md.rstrip().endswith("Separate decoder block."))
        resultado = json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))
        self.assertEqual(resultado["descricao"], descricao)

    def test_sem_descricao_nada_muda(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        r = self.agente(modelo, ExecutorFalso([ok(1), ok(24), ok(35)])).gerar()
        self.assertFalse(any("Designer's description" in p for _, _, p in modelo.pedidos))
        self.assertNotIn("requests", next(s for f, s in modelo.schemas if f == "decomposicao")["properties"])
        self.assertFalse((self.pasta / "descricao.md").exists())
        self.assertIsNone(json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))["descricao"])

    def test_checagem_do_contrato_entra_na_evidencia_e_aponta_o_top(self):
        # o valor errado nao aponta arquivo nenhum; a checagem estatica sim
        falhas = [("rv32i/add", False, "valor")]
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([ok(1), relatorio(casos=falhas), ok(24), ok(35)])
        self.agente(modelo, ex).gerar()
        pedido = next(p for f, a, p in modelo.pedidos if f == "correcao")
        self.assertIn("Contract check (static inspection of the text; a suggestion):", pedido)
        self.assertIn("must declare the port `instr_addr`", pedido)
        self.assertIn(("correcao", "src/cpu.vhd"), [(f, a) for f, a, _ in modelo.pedidos])
        self.assertNotIn("escolha", [f for f, _, _ in modelo.pedidos])

    def test_correcao_que_piora_e_desfeita_e_o_modelo_fica_sabendo(self):
        falhas = [(f"rv32i/c{k}", k < 20, "valor") for k in range(24)]
        pior = [(f"rv32i/c{k}", k < 10, "valor") for k in range(24)]
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO],
                              "escolha": ['{"file": "src/alu.vhd", "reason": "sra"}'] * 3})
        ex = ExecutorFalso([ok(1), relatorio(casos=falhas), relatorio(casos=pior),
                            ok(24), ok(35)])
        ag = self.agente(modelo, ex)
        r = ag.gerar()
        self.assertTrue(r.objetivo_atingido)
        self.assertEqual(r.iteracoes, 2)
        correcoes = [p for f, a, p in modelo.pedidos if f == "correcao"]
        self.assertNotIn("was reverted", correcoes[0])
        self.assertIn("made the result worse (10/24 casos instead of 20/24 casos) "
                      "and was reverted", correcoes[1])
        eventos = (r.sessao / "sessao.jsonl").read_text(encoding="utf-8")
        self.assertIn('"evento": "reversao"', eventos)
        self.assertTrue(any("alteracao desfeita" in l for l in self.linhas))

    def test_so_caminho_inexistente_vai_direto_para_o_top(self):
        obs = [("rv32i/add", False, "observacao"), ("rv32i/sub", False, "observacao")]
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        # compila (fumaca ok), mas na etapa RV32I o testbench nao acha os sinais
        ex = ExecutorFalso([ok(1), relatorio(casos=obs), ok(24), ok(35)])
        self.agente(modelo, ex).gerar()
        self.assertNotIn("escolha", [f for f, _, _ in modelo.pedidos])
        self.assertIn(("correcao", "src/cpu.vhd"),
                      [(f, a) for f, a, _ in modelo.pedidos])

    def test_orcamento_esgotado_ainda_julga_com_a_suite_completa(self):
        falha = relatorio(casos=[("rv32i/c0", False, "valor"), ("rv32i/c1", True, "")])
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        final = relatorio(casos=[("rv32i/c0", False, "valor")], veredito="reprovado")
        ex = ExecutorFalso([ok(1), falha, falha, falha, final])
        r = self.agente(modelo, ex, iteracoes=2).gerar()
        self.assertFalse(r.objetivo_atingido)
        self.assertEqual(r.veredito, "reprovado")
        self.assertEqual(ex.chamadas[-1]["etapa"], "rv32im")
        self.assertIsNone(ex.chamadas[-1]["casos"])

    def test_rv32i_exige_aprovacao_da_suite_oficial(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        final = relatorio(casos=[(f"rv32i/c{k}", True, "") for k in range(24)],
                          veredito="incompleto",
                          rv32i={"total": 24, "passou": 24, "falhou": 0})
        ex = ExecutorFalso([ok(1), ok(24), final])
        r = self.agente(modelo, ex, isa="rv32i").gerar()
        self.assertTrue(r.objetivo_atingido)
        self.assertEqual(r.veredito, "aprovado")

    def test_arquivo_protegido_alterado_recusa_o_veredito(self):
        selos = iter(["antes", "depois"])
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([ok(1), ok(24), ok(35)])
        with self.assertRaises(ErroIntegridade):
            self.agente(modelo, ex, protegidos=lambda: next(selos)).gerar()

    def test_escrita_fora_de_src_e_recusada(self):
        ag = self.agente(ModeloFalso(), ExecutorFalso([]))
        for rel in ("../fora.vhd", "src/../../fora.vhd", "cpu.toml", "src/Alu.vhd",
                    "src/sub/alu.vhd", "src/alu.py"):
            with self.subTest(rel=rel), self.assertRaises(ErroGeracao):
                ag._escrever(rel, "x")

    def test_pasta_com_conteudo_exige_forcar(self):
        (self.pasta).mkdir(parents=True)
        (self.pasta / "cpu.toml").write_text("", encoding="utf-8")
        with self.assertRaisesRegex(ErroGeracao, "--forcar"):
            self.agente(ModeloFalso(), ExecutorFalso([])).gerar()


class TestComandoGerar(unittest.TestCase):
    """`python -m rvgen gerar`: o que e recusado antes de gastar uma chamada."""

    def _main(self, argv, patches=None):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest import mock

        from rvgen import __main__ as cli
        saida, erros = io.StringIO(), io.StringIO()
        ps = [mock.patch.object(obj, nome, valor)
              for (obj, nome), valor in (patches or {}).items()]
        ps.append(mock.patch.dict("os.environ", {"RVGEN_PROVEDOR": "ollama",
                                                 "RVGEN_MODELO": ""}))
        for p in ps:
            p.start()
        try:
            with redirect_stdout(saida), redirect_stderr(erros):
                codigo = cli.main(argv)
        finally:
            for p in reversed(ps):
                p.stop()
        return codigo, saida.getvalue(), erros.getvalue()

    def test_isa_nao_julgada_sai_2_sem_chamar_nada(self):
        from rvgen import ollama as ol
        nunca = lambda *a, **k: self.fail("nao deveria procurar o Ollama")  # noqa: E731
        codigo, _, erros = self._main(
            ["gerar", "entregas/x"],
            {(ol, "localizar_servidor"): nunca,
             (ct, "ler_configuracao_cpu"): lambda: {"microarquitetura": "monociclo", "isa": "rv32imc", "descricao": ""}})
        self.assertEqual(codigo, 2)
        self.assertIn("nao e julgada pelo spec-riscv-test", erros)

    def test_pasta_fora_do_repositorio(self):
        with tempfile.TemporaryDirectory() as fora:
            codigo, _, erros = self._main(["gerar", fora])
        self.assertEqual(codigo, 2)
        self.assertIn("fora do repositorio", erros)

    def test_ponta_a_ponta_com_falsos(self):
        from rvgen import __main__ as cli
        from rvgen import ollama as ol
        from rvgen.config import REPO_ROOT

        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        executor = ExecutorFalso([ok(1), ok(24), ok(35)])
        with tempfile.TemporaryDirectory(dir=REPO_ROOT,
                                          prefix="_teste_rvgen_") as d:
            arquivo = Path(d).parent / f"{Path(d).name}_descricao.txt"
            arquivo.write_text("Use a separate immediate generator block.\n", encoding="utf-8")
            try:
                codigo, saida, erros = self._main(
                    ["gerar", d, "--modelo", "m:1",
                     "--descricao-arquivo", str(arquivo)],
                    {(cli.ex, "escolher_executor"): lambda *a, **k: executor,
                     (ol, "localizar_servidor"): lambda *a, **k: ("http://falso", "0.32.1"),
                     (ol, "modelos_instalados"): lambda *a, **k: ["m:1"],
                     (cli, "ClienteOllama"): lambda *a, **k: modelo,
                      (cli.Agente, "__init__"): _init_com_selo_fixo,
                      (ct, "ler_configuracao_cpu"): lambda: {
                          "microarquitetura": "monociclo", "isa": "rv32im", "descricao": ""}})
                self.assertFalse((Path(d) / "cpu.toml").exists())
                self.assertIn("separate immediate generator",
                              (Path(d) / "descricao.md").read_text(encoding="utf-8"))
            finally:
                arquivo.unlink()
        self.assertEqual(codigo, 0, f"stderr:\n{erros}\nstdout:\n{saida}")
        self.assertIn("APROVADO   (OBJETIVO ATINGIDO)", saida)
        self.assertIn("descricao: 41 caracteres", saida)
        self.assertIn("validar de novo: spec-riscv-test --cpu _teste_rvgen_", saida)

    def test_pasta_existente_nao_cita_sessao_que_nao_existe(self):
        from rvgen import __main__ as cli
        from rvgen import ollama as ol
        from rvgen.config import REPO_ROOT

        with tempfile.TemporaryDirectory(dir=REPO_ROOT,
                                          prefix="_teste_rvgen_") as d:
            (Path(d) / "cpu.toml").write_text("", encoding="utf-8")
            codigo, _, erros = self._main(
                ["gerar", d, "--modelo", "m:1"],
                {(cli.ex, "escolher_executor"): lambda *a, **k: ExecutorFalso([]),
                 (ol, "localizar_servidor"): lambda *a, **k: ("http://falso", "0.32.1"),
                 (ol, "modelos_instalados"): lambda *a, **k: ["m:1"],
                 (cli, "ClienteOllama"): lambda *a, **k: ModeloFalso(),
                 (cli.Agente, "__init__"): _init_com_selo_fixo})
            self.assertFalse((Path(d) / ".rvgen").exists())
        self.assertEqual(codigo, 2)
        self.assertIn("use --forcar", erros)
        self.assertNotIn("sessao em", erros)

    def test_descricao_vazia_e_recusada(self):
        from rvgen import ollama as ol
        nunca = lambda *a, **k: self.fail("nao deveria procurar o Ollama")  # noqa: E731
        codigo, _, erros = self._main(
                ["gerar", "x", "--descricao", "   "],
            {(ol, "localizar_servidor"): nunca})
        self.assertEqual(codigo, 2)
        self.assertIn("descricao esta vazia", erros)


_init_original = Agente.__init__


def _init_com_selo_fixo(self, **kw):
    """O Agente de verdade, mas sem hashear o rvverify real nem ler o catalogo."""
    _init_original(self, protegidos=lambda: "selo", caso_de_fumaca=lambda: "rv32i/add", **kw)


class TestRelator(unittest.TestCase):
    """A tela do `gerar`: tempo decorrido e contador vivo durante as esperas."""

    def test_cada_linha_leva_o_tempo_decorrido(self):
        import io
        from contextlib import redirect_stdout

        from rvgen.__main__ import Relator
        agora = iter([100.0, 100.0, 165.0])          # inicio, 1a linha, 2a linha
        r = Relator(interativo=False, relogio=lambda: next(agora))
        saida = io.StringIO()
        with redirect_stdout(saida):
            r.linha("[1/4] decompondo ...")
            r.linha("  pronto")
            r.fechar()
        self.assertEqual(saida.getvalue().splitlines(),
                         ["[00:00] [1/4] decompondo ...", "[01:05]   pronto"])

    def test_contador_vivo_so_no_terminal_e_para_na_linha_seguinte(self):
        import io
        import time
        from contextlib import redirect_stdout

        from rvgen.__main__ import Relator
        r = Relator(interativo=True)
        saida = io.StringIO()
        with redirect_stdout(saida):
            r.linha("  rvverify fumaca: compila? (1 caso) ...")
            time.sleep(1.3)
            r.progresso(512)
            time.sleep(1.1)
            r.linha("  pronto")
            depois = saida.getvalue()
            time.sleep(1.2)                              # o relogio parou mesmo
            self.assertEqual(saida.getvalue(), depois)
            r.fechar()
        self.assertIn("aguardando, 1 s", depois)
        self.assertIn("512 caracteres recebidos, 2 s", depois)
        self.assertTrue(depois.rstrip().endswith("pronto"))

    def test_cores_classificam_resultado_e_nova_interacao(self):
        from rvgen.__main__ import Relator
        r = Relator(interativo=False)
        r.colorido = True
        self.assertIn("\033[32m", r._colorir("  teste alu ok (1 s)"))
        self.assertIn("\033[33m", r._colorir("  triagem: corrigindo o testbench ..."))
        self.assertIn("\033[31m", r._colorir("  teste alu FALHOU (1 s)"))
        fluxo = r._colorir("  fluxo: ✓ Arquitetura ──▶ ● Componentes ──▶ ○ Testes")
        self.assertIn("\033[32m✓\033[0m", fluxo)
        self.assertIn("\033[33m●\033[0m", fluxo)


class TestValidarArquitetura(unittest.TestCase):

    def test_normaliza_e_recusa(self):
        blocos, _ = validar_arquitetura(json.loads(PLANO_VALIDO))
        self.assertEqual([b["name"] for b in blocos], ["alu", "regs", "cpu"])
        self.assertEqual(blocos[0]["file"], "src/alu.vhd")
        for bruta, motivo in (
                ({"blocks": [{"name": "data_ram", "responsibility": "x"},
                             {"name": "cpu", "responsibility": "x"}]}, "fornecido"),
                ({"blocks": [{"name": "alu", "responsibility": "x"}] * 2 +
                  [{"name": "cpu", "responsibility": "x"}]}, "repetido"),
                ({"blocks": [{"name": "alu", "responsibility": "x"},
                             {"name": "regs", "responsibility": "x"}]}, "cpu"),
                ({"blocks": [{"name": "../x", "responsibility": "x"}]}, "invalido"),
                ([], "blocks")):
            with self.subTest(motivo=motivo):
                blocos, m = validar_arquitetura(bruta)
                self.assertIsNone(blocos)
                self.assertIn(motivo, m)

    def test_ordena_dependencias_e_recusa_ciclo(self):
        plano = {"blocks": [
            {"name": "cpu", "responsibility": "top", "depends_on": ["decoder"]},
            {"name": "decoder", "responsibility": "decode", "depends_on": ["immediates"]},
            {"name": "immediates", "responsibility": "imm", "depends_on": []},
        ]}
        blocos, motivo = validar_arquitetura(plano)
        self.assertEqual(motivo, "")
        self.assertEqual([b["name"] for b in blocos], ["immediates", "decoder", "cpu"])
        plano["blocks"][2]["depends_on"] = ["decoder"]
        blocos, motivo = validar_arquitetura(plano)
        self.assertIsNone(blocos)
        self.assertIn("ciclo", motivo)



if __name__ == "__main__":
    unittest.main()
