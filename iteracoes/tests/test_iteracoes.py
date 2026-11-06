#!/usr/bin/env python3
"""Testes do app de iteracoes de specs (nucleo e servidor).

Cada teste monta um repositorio falso numa pasta temporaria, com copias das
specs reais em ``specs/`` e ``iteracoes/base/specs``: nada toca o
``iteracoes/`` nem o ``specs/`` de verdade.
"""

from __future__ import annotations

import http.client
import json
import re
import shutil
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from iteracoes.nucleo import (PAPEL_DOC, PAPEL_SISTEMA, PAPEL_SISTEMA_IM, PAPEL_TESTES, ErroIteracoes,
                              ErroNaoEncontrado, ErroPermissao, Repositorio)
from iteracoes.servidor import LIMITE_CORPO, criar_servidor
from rvgen.config import REPO_ROOT

SPECS_REAIS = REPO_ROOT / "specs"


def _copiar_md(origem: Path, destino: Path) -> None:
    destino.mkdir(parents=True)
    for arq in origem.glob("*.md"):
        shutil.copyfile(arq, destino / arq.name)


class BaseRepo(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="iteracoes_teste_")
        self.raiz = Path(self._tmp.name)
        _copiar_md(SPECS_REAIS, self.raiz / "specs")
        _copiar_md(SPECS_REAIS, self.raiz / "iteracoes" / "base" / "specs")
        self.repo = Repositorio(self.raiz)

    def tearDown(self):
        self._tmp.cleanup()

    def escrever(self, versao: str, rel: str, texto: str) -> None:
        (self.repo.pasta_da_versao(versao) / rel).write_text(texto, encoding="utf-8")

    def ler(self, versao: str, rel: str) -> str:
        return self.repo.ler_arquivo(versao, rel)


class TestCriar(BaseRepo):

    def test_ids_sequenciais_e_origens(self):
        a = self.repo.criar_iteracao("base", "primeira", "hipotese A")
        self.escrever("specs", "plan.md", "ativa diferente\n")
        b = self.repo.criar_iteracao("specs", "da ativa")
        self.escrever(a, "vhdl.md", "editada na it-001\n")
        c = self.repo.criar_iteracao(a, "da primeira")
        self.assertEqual((a, b, c), ("it-001", "it-002", "it-003"))
        self.assertEqual(self.ler(a, "cpu.md"), self.ler("base", "cpu.md"))
        self.assertEqual(self.ler(b, "plan.md"), "ativa diferente\n")
        self.assertEqual(self.ler(c, "vhdl.md"), "editada na it-001\n")
        meta = json.loads((self.raiz / "iteracoes" / a / "iteracao.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["id"], a)
        self.assertEqual(meta["nome"], "primeira")
        self.assertEqual(meta["origem"], "base")
        self.assertEqual(meta["notas"], "hipotese A")
        self.assertEqual(meta["experimentos"], [])
        self.assertRegex(meta["criada_em"], r"^\d{4}-\d{2}-\d{2}T")
        ids = [v["id"] for v in self.repo.listar()["versoes"]]
        self.assertEqual(ids, ["base", "specs", a, b, c])

    def test_copia_da_base_somente_leitura_fica_editavel(self):
        base = self.repo.pasta_base / "cpu.md"
        base.chmod(0o444)
        try:
            it = self.repo.criar_iteracao("base")
            self.repo.salvar_arquivo(it, "cpu.md", self.ler(it, "cpu.md") + "\nmais\n")
        finally:
            base.chmod(0o644)

    def test_copia_inclui_subpastas(self):
        (self.repo.pasta_base / "upstream").mkdir()
        (self.repo.pasta_base / "upstream" / "ref.adoc").write_text("x", encoding="utf-8")
        it = self.repo.criar_iteracao("base")
        self.assertTrue((self.repo.pasta_da_versao(it) / "upstream" / "ref.adoc").is_file())

    def test_origem_invalida(self):
        for origem in ("it-1", "../specs", "it-999", ""):
            with self.subTest(origem=origem), self.assertRaises(ErroIteracoes):
                self.repo.criar_iteracao(origem)

    def test_notas_e_nome(self):
        it = self.repo.criar_iteracao("base")
        meta = self.repo.atualizar_iteracao(it, nome="novo", notas="linha 1\nlinha 2")
        self.assertEqual((meta["nome"], meta["notas"]), ("novo", "linha 1\nlinha 2"))
        self.assertEqual(self.repo.ler_meta(it)["notas"], "linha 1\nlinha 2")


class TestEscritaECaminhos(BaseRepo):

    def test_base_recusa_escrita(self):
        antes = self.ler("base", "cpu.md")
        with self.assertRaises(ErroPermissao):
            self.repo.salvar_arquivo("base", "cpu.md", "apagado")
        self.assertEqual(self.ler("base", "cpu.md"), antes)

    def test_caminhos_invalidos(self):
        it = self.repo.criar_iteracao("base")
        ruins = ["../cpu.md", "../../specs/cpu.md", "/etc/cpu.md", "C:/x/cpu.md",
                 "C:\\x\\cpu.md", "sub\\cpu.md", "cpu.txt", "cpu", "x/../cpu.md",
                 "./cpu.md", "", ".md", "cpu.md/", "cpu.md\x00"]
        for rel in ruins:
            with self.subTest(rel=rel):
                with self.assertRaises(ErroIteracoes):
                    self.repo.ler_arquivo(it, rel)
                with self.assertRaises(ErroIteracoes):
                    self.repo.salvar_arquivo(it, rel, "x")

    def test_caractere_invalido_nao_apaga_nada(self):
        it = self.repo.criar_iteracao("base", "original", "notas")
        for versao in (it, "specs"):
            with self.subTest(versao=versao):
                antes = self.ler(versao, "cpu.md")
                with self.assertRaises(ErroIteracoes):
                    self.repo.salvar_arquivo(versao, "cpu.md", "novo \ud800 fim")
                self.assertEqual(self.ler(versao, "cpu.md"), antes)
        # nem backup da ativa: nada foi gravado
        self.assertEqual([v["id"] for v in self.repo.listar()["versoes"]][2:], [it])
        for campos in ({"nome": "x\udc00"}, {"notas": "y\ud800"}):
            with self.subTest(campos=campos), self.assertRaises(ErroIteracoes):
                self.repo.atualizar_iteracao(it, **campos)
        meta = self.repo.ler_meta(it)
        self.assertEqual((meta["nome"], meta["notas"]), ("original", "notas"))
        with self.assertRaises(ErroIteracoes):
            self.repo.criar_iteracao("base", "z\ud800")
        self.assertEqual(list(self.raiz.rglob("*.tmp")), [])

    def test_gravacao_atomica_mantem_o_antigo_se_falhar(self):
        from unittest import mock
        it = self.repo.criar_iteracao("base", "original")
        antes = self.ler(it, "cpu.md")
        with mock.patch("iteracoes.nucleo.os.replace", side_effect=OSError("disco cheio")):
            with self.assertRaises(OSError):
                self.repo.salvar_arquivo(it, "cpu.md", "novo texto")
            with self.assertRaises(OSError):
                self.repo.atualizar_iteracao(it, nome="outro")
        self.assertEqual(self.ler(it, "cpu.md"), antes)
        self.assertEqual(self.repo.ler_meta(it)["nome"], "original")
        self.assertEqual(list(self.raiz.rglob("*.tmp")), [])
        self.repo.salvar_arquivo(it, "cpu.md", "novo texto")
        self.assertEqual(self.ler(it, "cpu.md"), "novo texto")

    def test_arquivo_inexistente(self):
        with self.assertRaises(ErroNaoEncontrado):
            self.repo.ler_arquivo("specs", "nao_existe.md")

    def test_so_edita_existente_ou_recria_obrigatorio(self):
        it = self.repo.criar_iteracao("base")
        with self.assertRaises(ErroIteracoes):
            self.repo.salvar_arquivo(it, "novo.md", "x")
        self.assertFalse((self.repo.pasta_da_versao(it) / "novo.md").exists())
        (self.repo.pasta_da_versao(it) / "testes.md").unlink()
        self.assertEqual(self.repo.obrigatorios_ausentes(it), ["testes.md"])
        self.repo.salvar_arquivo(it, "testes.md", "regras\n")
        self.assertEqual(self.ler(it, "testes.md"), "regras\n")
        self.assertEqual(self.repo.obrigatorios_ausentes(it), [])

    def test_nomes_com_acento_e_subpasta(self):
        it = self.repo.criar_iteracao("base")
        pasta = self.repo.pasta_da_versao(it)
        (pasta / "notas").mkdir()
        (pasta / "notas" / "decisões v2.md").write_text("a\n", encoding="utf-8")
        (pasta / ".oculto.md").write_text("x\n", encoding="utf-8")
        rels = [a["rel"] for a in self.repo.arquivos(it)]
        self.assertIn("notas/decisões v2.md", rels)
        self.assertNotIn(".oculto.md", rels)
        self.repo.salvar_arquivo(it, "notas/decisões v2.md", "b\n")
        self.assertEqual(self.ler(it, "notas/decisões v2.md"), "b\n")

    def test_salvar_mantem_crlf(self):
        it = self.repo.criar_iteracao("base")
        caminho = self.repo.pasta_da_versao(it) / "plan.md"
        caminho.write_bytes(b"a\r\nb\r\n")
        self.assertEqual(self.ler(it, "plan.md"), "a\nb\n")
        self.repo.salvar_arquivo(it, "plan.md", "a\nb\nc\n")
        self.assertEqual(caminho.read_bytes(), b"a\r\nb\r\nc\r\n")

    def test_salvar_na_ativa_cria_backup_uma_vez(self):
        original = self.ler("specs", "plan.md")
        r1 = self.repo.salvar_arquivo("specs", "plan.md", original + "\nedicao 1\n")
        self.assertTrue(r1["alterado"])
        self.assertEqual(r1["backup"], "it-001")
        self.assertEqual(self.repo.ler_meta("it-001")["nome"], "antes-de-editar-specs")
        self.assertEqual(self.repo.ler_meta("it-001")["origem"], "specs")
        self.assertEqual(self.ler("it-001", "plan.md"), original)
        # o mesmo texto de novo: nada muda, nenhum backup
        r2 = self.repo.salvar_arquivo("specs", "plan.md", original + "\nedicao 1\n")
        self.assertEqual(r2, {"alterado": False, "backup": None})
        # nova edicao: a ativa (ja editada) ganha outro backup
        r3 = self.repo.salvar_arquivo("specs", "plan.md", "edicao 2\n")
        self.assertEqual(r3["backup"], "it-002")
        self.assertIn("edicao 1", self.ler("it-002", "plan.md"))
        self.assertEqual(self.ler("specs", "plan.md"), "edicao 2\n")

    def test_backup_reaproveita_um_igual(self):
        self.repo.criar_iteracao("specs", "antes-de-editar-specs")
        r = self.repo.salvar_arquivo("specs", "plan.md", "mudou\n")
        self.assertEqual(r["backup"], "it-001")
        self.assertEqual(len(self.repo.listar()["versoes"]), 3)

    def test_salvar_em_iteracao_nao_cria_backup(self):
        it = self.repo.criar_iteracao("base")
        r = self.repo.salvar_arquivo(it, "plan.md", "novo\n")
        self.assertEqual(r, {"alterado": True, "backup": None})


class TestComparar(BaseRepo):

    def test_diff_e_resumo(self):
        it = self.repo.criar_iteracao("base")
        texto = self.ler(it, "vhdl.md")
        self.repo.salvar_arquivo(it, "vhdl.md", texto + "\nlinha nova 1\nlinha nova 2\n")
        self.escrever(it, "extra.md", "so na iteracao\n")
        d = self.repo.diff("base", it, "vhdl.md")
        self.assertFalse(d["igual"])
        self.assertEqual((d["mais"], d["menos"]), (3, 0))
        self.assertIn("+linha nova 1", d["texto"])
        self.assertIn("--- base/vhdl.md", d["texto"])
        r = self.repo.resumo_diferencas("base", it)
        estados = {a["rel"]: a["estado"] for a in r["arquivos"]}
        self.assertEqual(estados["vhdl.md"], "alterado")
        self.assertEqual(estados["cpu.md"], "igual")
        self.assertEqual(estados["extra.md"], "so em B")
        self.assertEqual(r["mudados"], 2)
        inverso = self.repo.resumo_diferencas(it, "base")
        self.assertEqual({a["rel"]: a["estado"] for a in inverso["arquivos"]}["extra.md"], "so em A")

    def test_versoes_iguais(self):
        r = self.repo.resumo_diferencas("base", "specs")
        self.assertEqual(r["mudados"], 0)
        self.assertTrue(self.repo.diff("base", "specs", "cpu.md")["igual"])


class TestAnalise(BaseRepo):

    def _niveis(self, versao, trecho):
        return [c["nivel"] for c in self.repo.analisar(versao)["checagens"]
                if trecho in c["mensagem"]]

    def test_specs_reais_sem_erro(self):
        a = self.repo.analisar("specs")
        self.assertEqual(a["contagem"]["erro"], 0, a["checagens"])
        self.assertTrue(a["prompt"]["ok"])
        self.assertGreater(a["prompt"]["sistema"]["chars"], 1000)
        self.assertGreater(a["prompt"]["testes"]["chars"], a["prompt"]["sistema"]["chars"])
        self.assertEqual(a["variacao_vs_base"]["sistema"], 0.0)

    def test_papel_dos_arquivos(self):
        papeis = {a["rel"]: a["papel"] for a in self.repo.analisar("base")["arquivos"]}
        for rel in ("cpu.md", "vhdl.md", "riscv-rv32i.md"):
            self.assertEqual(papeis[rel], PAPEL_SISTEMA)
        self.assertEqual(papeis["testes.md"], PAPEL_TESTES)
        for rel in ("constitution.md", "plan.md", "spec.md"):
            self.assertEqual(papeis[rel], PAPEL_DOC)
        arq = next(a for a in self.repo.analisar("base")["arquivos"] if a["rel"] == "cpu.md")
        self.assertEqual(arq["tokens"], round(arq["chars"] / 4))

    def test_referencia_do_m_so_conta_com_rv32im(self):
        papeis = {a["rel"]: a["papel"] for a in self.repo.analisar("base")["arquivos"]}
        self.assertEqual(papeis["riscv-rv32m.md"], PAPEL_SISTEMA_IM)
        # RV32I: o arquivo do M nao e obrigatorio e nao entra no prompt
        it = self.repo.criar_iteracao("base")
        (self.repo.pasta_da_versao(it) / "riscv-rv32m.md").unlink()
        self.assertEqual(self.repo.analisar(it)["contagem"]["erro"], 0)
        self.assertNotIn("RV32M Implementation Reference", self.repo.prompt(it)["sistema"])
        # RV32IM sem o arquivo: erro na analise e ele aparece como ausente
        self.escrever(it, "cpu.md", self.ler(it, "cpu.md").replace(
            "- RV32I single cycle", "- RV32IM single cycle", 1))
        a = self.repo.analisar(it)
        self.assertEqual(a["prompt"]["isa"], "rv32im")
        self.assertTrue(any(c["nivel"] == "erro" and c["arquivo"] == "riscv-rv32m.md"
                            for c in a["checagens"]), a["checagens"])
        self.assertIn("riscv-rv32m.md", self.repo.obrigatorios_ausentes(it))
        # o app pode recriar o arquivo; com ele, o prompt traz o M
        self.repo.salvar_arquivo(it, "riscv-rv32m.md", self.ler("base", "riscv-rv32m.md"))
        self.assertEqual(self.repo.analisar(it)["contagem"]["erro"], 0)
        self.assertIn("RV32M Implementation Reference", self.repo.prompt(it)["sistema"])

    def test_generic_na_entidade_e_erro(self):
        it = self.repo.criar_iteracao("base")
        cpu = self.ler(it, "cpu.md").replace(
            "entity cpu is", "entity cpu is\n    generic(RV32M_ENABLE : boolean := true);", 1)
        self.repo.salvar_arquivo(it, "cpu.md", cpu)
        self.assertEqual(self._niveis(it, "generic"), ["erro"])

    def test_porta_faltando_e_erro(self):
        it = self.repo.criar_iteracao("base")
        cpu = self.ler(it, "cpu.md").replace("data_width :", "largura :", 1)
        self.repo.salvar_arquivo(it, "cpu.md", cpu)
        self.assertEqual(self._niveis(it, "\"data_width\""), ["erro"])

    def test_entidade_ausente_e_erro(self):
        it = self.repo.criar_iteracao("base")
        cpu = re.sub(r"entity cpu is.*?end cpu;", "(sem entidade)", self.ler(it, "cpu.md"),
                     flags=re.DOTALL)
        self.repo.salvar_arquivo(it, "cpu.md", cpu)
        self.assertEqual(self._niveis(it, "entity cpu is"), ["erro"])

    def test_isa_ambigua_e_erro(self):
        it = self.repo.criar_iteracao("base")
        # duas linhas de declaracao com ISAs diferentes: o rvgen recusa
        self.repo.salvar_arquivo(it, "cpu.md", self.ler(it, "cpu.md") + "\n- RV32IM pipeline\n")
        self.assertIn("erro", self._niveis(it, "ISA/microarquitetura"))
        p = self.repo.prompt(it)
        self.assertTrue(p["ok"])
        self.assertIsNotNone(p["aviso"])

    def test_req_vira_aviso_so_nos_arquivos_da_ia(self):
        it = self.repo.criar_iteracao("base")
        self.repo.salvar_arquivo(it, "vhdl.md", self.ler(it, "vhdl.md") + "\n-- REQ: FR-RV-01\n")
        self.repo.salvar_arquivo(it, "plan.md", self.ler(it, "plan.md") + "\n-- REQ: FR-RV-02\n")
        checs = [c for c in self.repo.analisar(it)["checagens"] if "REQ" in c["mensagem"]]
        self.assertEqual([(c["nivel"], c["arquivo"]) for c in checs], [("aviso", "vhdl.md")])

    def test_arquivo_obrigatorio_ausente_ou_vazio(self):
        it = self.repo.criar_iteracao("base")
        (self.repo.pasta_da_versao(it) / "testes.md").unlink()
        self.repo.salvar_arquivo(it, "vhdl.md", "   \n")
        a = self.repo.analisar(it)
        erros = {c["arquivo"]: c["mensagem"] for c in a["checagens"] if c["nivel"] == "erro"}
        self.assertIn("ausente", erros["testes.md"])
        self.assertIn("vazio", erros["vhdl.md"])
        self.assertIsNone(a["prompt"]["testes"])

    def test_rvverify_vira_info(self):
        it = self.repo.criar_iteracao("base")
        self.repo.salvar_arquivo(it, "vhdl.md", self.ler(it, "vhdl.md") + "\nO rvverify decide.\n")
        checs = [c for c in self.repo.analisar(it)["checagens"]
                 if c["arquivo"] == "vhdl.md" and "rvverify" in c["mensagem"]]
        self.assertEqual([c["nivel"] for c in checs], ["info"])

    def test_prompt_muda_de_tamanho_ao_editar_cpu_md(self):
        it = self.repo.criar_iteracao("base")
        antes = self.repo.analisar(it)["prompt"]["sistema"]["chars"]
        extra = "\nRegra nova da iteracao: use nomes curtos.\n"
        self.repo.salvar_arquivo(it, "cpu.md", self.ler(it, "cpu.md") + extra)
        a = self.repo.analisar(it)
        self.assertGreaterEqual(a["prompt"]["sistema"]["chars"] - antes, len(extra.strip()))
        self.assertGreater(a["variacao_vs_base"]["sistema"], 0)
        self.assertIn("Regra nova da iteracao", self.repo.prompt(it)["sistema"])
        self.assertNotIn("Regra nova da iteracao", self.repo.prompt("base")["sistema"])


class TestPromover(BaseRepo):

    def test_promover_cria_backup_e_copia(self):
        ativa_antes = self.ler("specs", "vhdl.md")
        self.escrever("specs", "so_na_ativa.md", "fica\n")
        it = self.repo.criar_iteracao("base", "melhor")
        self.repo.salvar_arquivo(it, "vhdl.md", "VHDL DA ITERACAO\n")
        r = self.repo.promover(it)
        self.assertEqual(r["backup"], "it-002")
        self.assertEqual(self.ler(r["backup"], "so_na_ativa.md"), "fica\n")
        self.assertEqual(self.repo.ler_meta(r["backup"])["nome"], f"antes-de-promover-{it}")
        self.assertEqual(self.ler(r["backup"], "vhdl.md"), ativa_antes)
        self.assertEqual(self.ler("specs", "vhdl.md"), "VHDL DA ITERACAO\n")
        self.assertIn("vhdl.md", r["copiados"])
        self.assertEqual(r["mantidos"], ["so_na_ativa.md"])
        self.assertTrue(any(v["id"] == it and v["igual_a_ativa"] is False
                            for v in self.repo.listar()["versoes"]))
        # a base nunca muda
        self.assertEqual(self.ler("base", "vhdl.md"), ativa_antes)

    def test_so_iteracao_pode_ser_promovida(self):
        for versao in ("base", "specs"):
            with self.subTest(versao=versao), self.assertRaises(ErroIteracoes):
                self.repo.promover(versao)


class TestExperimentos(BaseRepo):

    def test_vincular_e_ler_resultado(self):
        it = self.repo.criar_iteracao("base")
        self.repo.vincular_experimento(it, "it001_teste")
        self.repo.vincular_experimento(it, "it001_teste")
        self.assertEqual(self.repo.ler_meta(it)["experimentos"], ["it001_teste"])
        vazio = self.repo.resultado_experimento("it001_teste")
        self.assertFalse(vazio["existe"])
        rvgen = self.raiz / "experimentos" / "it001_teste" / ".rvgen"
        for nome, veredito in (("sessao-20261001-100000", "reprovado"),
                               ("sessao-20261002-100000", "aprovado")):
            (rvgen / nome).mkdir(parents=True)
            (rvgen / nome / "resultado.json").write_text(json.dumps(
                {"veredito": veredito, "chamadas": 42, "tokens_entrada": 1000,
                 "tokens_saida": 200}), encoding="utf-8")
            (rvgen / nome / "sessao.jsonl").write_text(json.dumps(
                {"evento": "inicio", "specs": f"iteracoes/{it}/specs"}) + "\n", encoding="utf-8")
        r = self.repo.resultado_experimento("it001_teste")
        self.assertEqual(r["sessao"], "sessao-20261002-100000")
        self.assertEqual(r["resultado"]["veredito"], "aprovado")
        self.assertEqual(r["resultado"]["chamadas"], 42)
        self.assertEqual(r["specs"], f"iteracoes/{it}/specs")
        self.assertEqual(r["sessoes"], 2)
        self.repo.desvincular_experimento(it, "it001_teste")
        self.assertEqual(self.repo.ler_meta(it)["experimentos"], [])

    def test_sessao_retomada_mostra_a_sessao_inteira(self):
        sessao = self.raiz / "experimentos" / "retomado" / ".rvgen" / "sessao-20261003-100000"
        sessao.mkdir(parents=True)
        (sessao / "resultado.json").write_text(json.dumps(
            {"veredito": "aprovado", "chamadas": 2, "tokens_entrada": 20, "tokens_saida": 2,
             "segundos": 78.8, "retomada": True}), encoding="utf-8")
        eventos = [{"evento": "inicio", "specs": "specs"}] + [
            {"evento": "llm", "tokens_entrada": 10, "tokens_saida": 1, "segundos": 6}] * 3
        (sessao / "sessao.jsonl").write_text(
            "".join(json.dumps(e) + "\n" for e in eventos), encoding="utf-8")
        res = self.repo.resultado_experimento("retomado")["resultado"]
        self.assertEqual((res["chamadas"], res["tokens_entrada"], res["tokens_saida"]),
                         (3, 30, 3))
        self.assertEqual(res["segundos"], 18.0)
        self.assertTrue(res["sessao_inteira"])

    def test_nome_de_experimento_invalido(self):
        it = self.repo.criar_iteracao("base")
        for nome in ("../x", "a/b", "", "..", "a\\b"):
            with self.subTest(nome=nome), self.assertRaises(ErroIteracoes):
                self.repo.vincular_experimento(it, nome)


class TestServidor(BaseRepo):

    def setUp(self):
        super().setUp()
        self.srv = criar_servidor(self.raiz, 0, token="token-de-teste")
        self.fio = threading.Thread(target=self.srv.serve_forever, daemon=True)
        self.fio.start()
        self.base_url = f"http://127.0.0.1:{self.srv.porta}"

    def tearDown(self):
        self.srv.shutdown()
        self.srv.server_close()
        self.fio.join(5)
        super().tearDown()

    def pedir(self, caminho, corpo=None, cabecalhos=None):
        dados = json.dumps(corpo).encode("utf-8") if corpo is not None else None
        req = urllib.request.Request(self.base_url + caminho, data=dados,
                                     method="POST" if dados is not None else "GET")
        if dados is not None:
            req.add_header("Content-Type", "application/json")
        for k, v in (cabecalhos or {}).items():
            req.add_header(k, v)
        try:
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.status, r.read().decode("utf-8"), dict(r.headers)
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8"), dict(e.headers)

    def test_pagina_com_token(self):
        status, html, cab = self.pedir("/")
        self.assertEqual(status, 200)
        self.assertIn('<meta name="token" content="token-de-teste">', html)
        self.assertNotIn("__TOKEN_ITERACOES__", html)
        self.assertIn("Prompt que a IA recebe", html)
        self.assertIn("Content-Security-Policy", cab)
        self.assertEqual(self.srv.server_address[0], "127.0.0.1")

    def test_post_sem_token_e_403(self):
        status, corpo, _ = self.pedir("/api/iteracoes", {"origem": "base"})
        self.assertEqual(status, 403)
        self.assertIn("token", json.loads(corpo)["erro"])
        status, _, _ = self.pedir("/api/iteracoes", {"origem": "base"}, {"X-Token": "errado"})
        self.assertEqual(status, 403)
        self.assertEqual(self.repo.listar()["versoes"][2:], [])

    def test_post_com_token_cria_iteracao(self):
        status, corpo, _ = self.pedir("/api/iteracoes", {"origem": "base", "nome": "via http"},
                                      {"X-Token": "token-de-teste",
                                       "Origin": self.base_url})
        self.assertEqual(status, 201, corpo)
        self.assertEqual(json.loads(corpo), {"id": "it-001"})
        status, corpo, _ = self.pedir("/api/versoes")
        self.assertEqual([v["nome"] for v in json.loads(corpo)["versoes"]][-1], "via http")

    def test_origin_ou_host_estranhos_sao_403(self):
        status, _, _ = self.pedir("/api/iteracoes", {"origem": "base"},
                                  {"X-Token": "token-de-teste", "Origin": "http://evil.example"})
        self.assertEqual(status, 403)
        status, _, _ = self.pedir("/api/versoes", cabecalhos={"Host": "evil.example"})
        self.assertEqual(status, 403)

    def test_caminho_malicioso_e_400(self):
        for rel in ("../cpu.md", "..%2Fcpu.md", "%2Fetc%2Fpasswd.md", "cpu.txt"):
            with self.subTest(rel=rel):
                status, _, _ = self.pedir(f"/api/arquivo?versao=specs&rel={rel}")
                self.assertEqual(status, 400)
        status, _, _ = self.pedir("/api/arquivo", {"versao": "specs", "rel": "../x.md",
                                                   "texto": "x"}, {"X-Token": "token-de-teste"})
        self.assertEqual(status, 400)
        status, _, _ = self.pedir("/api/arquivo?versao=..&rel=cpu.md")
        self.assertEqual(status, 400)

    def test_base_e_403_e_corpo_grande_e_413(self):
        status, _, _ = self.pedir("/api/arquivo", {"versao": "base", "rel": "cpu.md", "texto": "x"},
                                  {"X-Token": "token-de-teste"})
        self.assertEqual(status, 403)
        # so o cabecalho: o servidor recusa sem ler o corpo
        con = http.client.HTTPConnection("127.0.0.1", self.srv.porta, timeout=10)
        try:
            con.putrequest("POST", "/api/arquivo")
            con.putheader("Content-Type", "application/json")
            con.putheader("X-Token", "token-de-teste")
            con.putheader("Content-Length", str(LIMITE_CORPO + 1))
            con.endheaders()
            self.assertEqual(con.getresponse().status, 413)
        finally:
            con.close()

    def test_corpo_malformado_e_400(self):
        it = self.repo.criar_iteracao("base")
        antes = self.ler(it, "cpu.md")
        corpos = [b"[" * 200000 + b"]" * 200000, b"1" * 5000, b"\xff\xfe", b"{",
                  ('{"versao": "%s", "rel": "cpu.md", "texto": "a\\ud800"}' % it).encode()]
        for corpo in corpos:
            with self.subTest(corpo=corpo[:20]):
                con = http.client.HTTPConnection("127.0.0.1", self.srv.porta, timeout=10)
                try:
                    con.request("POST", "/api/arquivo", corpo,
                                {"Content-Type": "application/json", "X-Token": "token-de-teste"})
                    r = con.getresponse()
                    resposta = json.loads(r.read())
                finally:
                    con.close()
                self.assertEqual(r.status, 400, resposta)
                self.assertNotIn("erro interno", resposta["erro"])
        self.assertEqual(self.ler(it, "cpu.md"), antes)

    def test_api_de_leitura(self):
        for caminho in ("/api/arquivos?versao=base", "/api/arquivo?versao=base&rel=cpu.md",
                        "/api/analise?versao=specs", "/api/prompt?versao=specs",
                        "/api/resumo?a=base&b=specs", "/api/diff?a=base&b=specs&rel=cpu.md",
                        "/api/experimento?nome=nada"):
            with self.subTest(caminho=caminho):
                status, corpo, cab = self.pedir(caminho)
                self.assertEqual(status, 200, corpo)
                self.assertTrue(cab["Content-Type"].startswith("application/json"))
                json.loads(corpo)
        status, _, _ = self.pedir("/api/nada")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
