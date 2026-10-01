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
                          validar_arquitetura)
from rvgen.executor import Execucao, Executor
from rvgen.llm import Resposta
from rvverify.manifest import load_manifest


def vhdl(nome: str, marca: str = "") -> str:
    return (f"```vhdl\n-- REQ: FR-RV-04\nentity {nome} is\nend {nome};\n"
            f"architecture rtl of {nome} is\nbegin\n  -- {marca}\nend rtl;\n```")


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
        if "Decompose this" in texto:
            return "decomposicao", "-"
        if m := re.search(r"Which ONE file", texto):
            return "escolha", "-"
        if m := re.search(r"^Fix (src/\w+\.vhd)", texto, re.MULTILINE):
            return "correcao", m.group(1)
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
        elif fase == "decomposicao":
            texto = "nao sei"
        else:
            texto = '{"file": "src/cpu_top.vhd", "reason": "?"}'
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

    def __init__(self, relatorios: list[dict]) -> None:
        super().__init__()
        self.relatorios = list(relatorios)
        self.chamadas: list[dict] = []

    def rodar(self, pasta, *, json_saida, workdir, build_root, casos=None,
              etapa="ambas", timeout=0):
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


PLANO_VALIDO = json.dumps({"blocks": [
    {"name": "cpu_top", "responsibility": "top", "ports": [], "satisfies": ["FR-RV-05"],
     "design_rationale": "contract"},
    {"name": "alu", "responsibility": "alu", "ports": [], "satisfies": ["FR-RV-04"],
     "design_rationale": "area"},
    {"name": "regs", "responsibility": "register file", "ports": [],
     "satisfies": ["FR-RV-06"], "design_rationale": "vpi"}],
    "notes": "ok"})


class TestAgente(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name) / "gerada"
        self.linhas: list[str] = []

    def tearDown(self):
        self._tmp.cleanup()

    def agente(self, modelo, executor, *, isa="rv32im", tipo="monociclo",
               iteracoes=5, protegidos=None, **kw):
        return Agente(cliente=modelo, executor=executor, pasta=self.pasta,
                      tipo=ct.TIPOS[tipo], isa=isa, iteracoes=iteracoes,
                      relatar=self.linhas.append,
                      protegidos=protegidos or (lambda: "selo"),
                      caso_de_fumaca=lambda: "rv32i/add", **kw)

    def test_caminho_feliz_rv32im_e_sessao_registrada(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        ex = ExecutorFalso([ok(1), ok(24), ok(35)])
        r = self.agente(modelo, ex).gerar()

        self.assertTrue(r.objetivo_atingido)
        self.assertEqual((r.veredito, r.iteracoes), ("aprovado", 0))
        # fumaca com 1 caso, etapa RV32I, completa; a completa E o veredito
        self.assertEqual([(c["etapa"], c["casos"]) for c in ex.chamadas],
                         [("rv32i", ["rv32i/add"]), ("rv32i", None), ("ambas", None)])
        # o top e escrito por ultimo, mesmo proposto primeiro pelo modelo
        escritos = [a for f, a, _ in modelo.pedidos if f == "escrita"]
        self.assertEqual(escritos, ["src/alu.vhd", "src/regs.vhd", "src/cpu_top.vhd"])
        arq = json.loads((self.pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual(arq["origem"], "modelo")
        m = load_manifest(self.pasta)
        self.assertEqual([p.name for p in m.source_paths()][-3:],
                         ["alu.vhd", "regs.vhd", "cpu_top.vhd"])

        eventos = [json.loads(l) for l in
                   (r.sessao / "sessao.jsonl").read_text(encoding="utf-8").splitlines()]
        llm = [e for e in eventos if e["evento"] == "llm"]
        self.assertEqual(llm[0]["mensagens"][0], {"role": "system", "content": "@contrato.txt"})
        self.assertTrue((r.sessao / "contrato.txt").read_text(encoding="utf-8").startswith("You write VHDL"))
        resultado = json.loads((r.sessao / "resultado.json").read_text(encoding="utf-8"))
        self.assertEqual((resultado["veredito"], resultado["modelo"]), ("aprovado", "falso:1b"))

    def test_decomposicao_invalida_cai_no_padrao_do_tipo(self):
        modelo = ModeloFalso({"decomposicao": ['{"blocks": []}', "texto sem json"]})
        self.agente(modelo, ExecutorFalso([ok(1), ok(24), ok(35)])).gerar()
        arq = json.loads((self.pasta / "architecture.json").read_text(encoding="utf-8"))
        self.assertEqual(arq["origem"], "padrao")
        self.assertEqual([b["name"] for b in arq["blocks"]],
                         [b.name for b in ct.TIPOS["monociclo"].blocos])
        self.assertTrue(any("decomposicao padrao" in l for l in self.linhas))

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

        # nos tres tipos de pedido, com o contrato por cima
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
        self.assertIn("must instantiate the label `register_file` exactly", pedido)
        self.assertIn(("correcao", "src/cpu_top.vhd"), [(f, a) for f, a, _ in modelo.pedidos])
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
        self.assertIn(("correcao", "src/cpu_top.vhd"),
                      [(f, a) for f, a, _ in modelo.pedidos])

    def test_orcamento_esgotado_ainda_julga_com_a_suite_completa(self):
        falha = relatorio(casos=[("rv32i/c0", False, "valor"), ("rv32i/c1", True, "")])
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        final = relatorio(casos=[("rv32i/c0", False, "valor")], veredito="reprovado")
        ex = ExecutorFalso([ok(1), falha, falha, falha, final])
        r = self.agente(modelo, ex, iteracoes=2).gerar()
        self.assertFalse(r.objetivo_atingido)
        self.assertEqual(r.veredito, "reprovado")
        self.assertEqual(ex.chamadas[-1], {"etapa": "ambas", "casos": None, "rotulo": "final"})

    def test_rv32i_aceita_incompleto_so_com_a_base_inteira(self):
        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        final = relatorio(casos=[(f"rv32i/c{k}", True, "") for k in range(24)],
                          veredito="incompleto",
                          rv32i={"total": 24, "passou": 24, "falhou": 0})
        ex = ExecutorFalso([ok(1), ok(24), final])
        r = self.agente(modelo, ex, isa="rv32i").gerar()
        self.assertTrue(r.objetivo_atingido)
        self.assertEqual(r.veredito, "incompleto")
        self.assertIsNone(load_manifest(self.pasta).design.rv32m_generic)

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
            ["gerar", "entregas/x", "--tipo", "monociclo", "--isa", "rv32imc"],
            {(ol, "localizar_servidor"): nunca})
        self.assertEqual(codigo, 2)
        self.assertIn("nao e julgada pelo rvverify", erros)

    def test_pasta_fora_do_repositorio(self):
        with tempfile.TemporaryDirectory() as fora:
            codigo, _, erros = self._main(["gerar", fora, "--tipo", "monociclo",
                                           "--isa", "rv32im"])
        self.assertEqual(codigo, 2)
        self.assertIn("fora do repositorio", erros)

    def test_ponta_a_ponta_com_falsos(self):
        from rvgen import __main__ as cli
        from rvgen import ollama as ol
        from rvgen.config import REPO_ROOT

        modelo = ModeloFalso({"decomposicao": [PLANO_VALIDO]})
        executor = ExecutorFalso([ok(1), ok(24), ok(35)])
        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "experimentos",
                                         prefix="_teste_rvgen_") as d:
            arquivo = Path(d).parent / f"{Path(d).name}_descricao.txt"
            arquivo.write_text("Use a separate immediate generator block.\n", encoding="utf-8")
            try:
                codigo, saida, erros = self._main(
                    ["gerar", d, "--tipo", "monociclo", "--isa", "rv32im", "--modelo", "m:1",
                     "--descricao-arquivo", str(arquivo)],
                    {(cli.ex, "escolher_executor"): lambda *a, **k: executor,
                     (ol, "localizar_servidor"): lambda *a, **k: ("http://falso", "0.32.1"),
                     (ol, "modelos_instalados"): lambda *a, **k: ["m:1"],
                     (cli, "ClienteOllama"): lambda *a, **k: modelo,
                     (cli.Agente, "__init__"): _init_com_selo_fixo})
                self.assertTrue((Path(d) / "cpu.toml").exists())
                self.assertIn("separate immediate generator",
                              (Path(d) / "descricao.md").read_text(encoding="utf-8"))
            finally:
                arquivo.unlink()
        self.assertEqual(codigo, 0, erros)
        self.assertIn("APROVADO   (OBJETIVO ATINGIDO)", saida)
        self.assertIn("descricao: 41 caracteres", saida)
        self.assertIn("validar de novo: python -m rvverify experimentos/_teste_rvgen_", saida)

    def test_pasta_existente_nao_cita_sessao_que_nao_existe(self):
        from rvgen import __main__ as cli
        from rvgen import ollama as ol
        from rvgen.config import REPO_ROOT

        with tempfile.TemporaryDirectory(dir=REPO_ROOT / "experimentos",
                                         prefix="_teste_rvgen_") as d:
            (Path(d) / "cpu.toml").write_text("", encoding="utf-8")
            codigo, _, erros = self._main(
                ["gerar", d, "--tipo", "monociclo", "--isa", "rv32im", "--modelo", "m:1"],
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
            ["gerar", "x", "--tipo", "monociclo", "--isa", "rv32im", "--descricao", "   "],
            {(ol, "localizar_servidor"): nunca})
        self.assertEqual(codigo, 2)
        self.assertIn("descricao esta vazia", erros)


_init_original = Agente.__init__


def _init_com_selo_fixo(self, **kw):
    """O Agente de verdade, mas sem hashear o rvverify real nem ler o catalogo."""
    _init_original(self, protegidos=lambda: "selo", caso_de_fumaca=lambda: "rv32i/add", **kw)


class TestValidarArquitetura(unittest.TestCase):

    def test_normaliza_e_recusa(self):
        blocos, _ = validar_arquitetura(json.loads(PLANO_VALIDO))
        self.assertEqual([b["name"] for b in blocos], ["alu", "regs", "cpu_top"])
        self.assertEqual(blocos[0]["file"], "src/alu.vhd")
        for bruta, motivo in (
                ({"blocks": [{"name": "data_ram", "responsibility": "x"},
                             {"name": "cpu_top", "responsibility": "x"}]}, "fornecido"),
                ({"blocks": [{"name": "alu", "responsibility": "x"}] * 2 +
                  [{"name": "cpu_top", "responsibility": "x"}]}, "repetido"),
                ({"blocks": [{"name": "alu", "responsibility": "x"},
                             {"name": "regs", "responsibility": "x"}]}, "cpu_top"),
                ({"blocks": [{"name": "../x", "responsibility": "x"}]}, "invalido"),
                ([], "blocks")):
            with self.subTest(motivo=motivo):
                blocos, m = validar_arquitetura(bruta)
                self.assertIsNone(blocos)
                self.assertIn(motivo, m)


if __name__ == "__main__":
    unittest.main()
