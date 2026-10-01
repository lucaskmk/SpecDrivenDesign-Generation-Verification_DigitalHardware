#!/usr/bin/env python3
"""Testes do `rvgen comparar` e da pasta `experimentos/`.

REQ: FR-RV-51 (tabela lida dos registros, custo como estimativa), FR-RV-47
e ADR-019 (nome sem diretorio vai para experimentos/).

Os experimentos sao montados a mao, no mesmo formato que `rvgen gerar`
grava: `resultado.json` da sessao e o relatorio final do rvverify. Nada
aqui roda modelo, GHDL ou rede.
"""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from rvgen import comparar as cmp
from rvgen.__main__ import main, resolver_pasta
from rvgen.config import REPO_ROOT

PRECOS = {"openai/gpt-5.6-luna": (0.20e-6, 1.20e-6)}


def experimento(raiz: Path, nome: str, sessao: str, *, provedor="ollama",
                modelo="qwen2.5-coder:14b", isa="rv32im", veredito="aprovado",
                placar="35/35 casos", por_etapa=None, pulado=(), tokens=(1000, 100),
                exemplo=None, descricao=None) -> Path:
    s = raiz / nome / ".rvgen" / f"sessao-{sessao}"
    (s / "rvverify").mkdir(parents=True)
    rel = {"veredito": veredito, "por_etapa": por_etapa if por_etapa is not None else
           {"rv32i": {"passou": 24, "total": 24, "falhou": 0},
            "rv32m": {"passou": 11, "total": 11, "falhou": 0}},
           "pulado": list(pulado)}
    (s / "rvverify" / "final.json").write_text(json.dumps([rel]), encoding="utf-8")
    (s / "resultado.json").write_text(json.dumps({
        "veredito": veredito, "placar": placar, "iteracoes": 3, "chamadas": 9,
        "tokens_entrada": tokens[0], "tokens_saida": tokens[1], "segundos": 600,
        "provedor": provedor, "modelo": modelo, "tipo": "monociclo", "isa": isa,
        "exemplo": exemplo, "descricao": descricao,
        "relatorio": f".rvgen/sessao-{sessao}/rvverify/final.json",
    }), encoding="utf-8")
    return s


class TestComparar(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_mais_recente_por_experimento_ou_todas(self):
        experimento(self.raiz, "local", "20260101-000000")
        nova = experimento(self.raiz, "local", "20260102-000000")
        (self.raiz / "local" / ".rvgen" / "sessao-20260103-000000").mkdir()   # parou sem resultado
        self.assertEqual(cmp.sessoes([self.raiz]), [nova])
        self.assertEqual(len(cmp.sessoes([self.raiz], todas=True)), 2)
        self.assertEqual(cmp.sessoes([self.raiz / "local"]), [nova])        # a pasta do experimento
        self.assertEqual(cmp.sessoes([self.raiz / "nao_existe"]), [])

    def test_placar_por_etapa_vem_do_relatorio_final(self):
        ok = cmp.linha_de(experimento(self.raiz, "ok", "1"), None)
        self.assertEqual((ok.veredito, ok.rv32i, ok.rv32im), ("APROVADO", "24/24", "11/11"))
        falhou = cmp.linha_de(experimento(
            self.raiz, "falhou", "1", veredito="reprovado", placar="nao compilou",
            por_etapa={}), None)
        self.assertEqual((falhou.rv32i, falhou.rv32im), ("nao compilou", "nao compilou"))
        # FR-RV-11: base reprovada, a etapa M e pulada
        base = cmp.linha_de(experimento(
            self.raiz, "base", "1", veredito="reprovado", placar="20/24 casos",
            por_etapa={"rv32i": {"passou": 20, "total": 24, "falhou": 4}},
            pulado=["etapa RV32IM pulada: a base reprovou"]), None)
        self.assertEqual((base.rv32i, base.rv32im), ("20/24", "pulada"))
        so_i = cmp.linha_de(experimento(self.raiz, "so_i", "1", isa="rv32i"), None)
        self.assertEqual(so_i.rv32im, "-")

    def test_custo_local_estimado_e_desconhecido(self):
        local = cmp.linha_de(experimento(self.raiz, "local", "1"), PRECOS)
        self.assertEqual((local.custo, local.custo_usd), ("0 (local)", 0.0))
        gpt = cmp.linha_de(experimento(
            self.raiz, "gpt", "1", provedor="openrouter",
            modelo="openai/gpt-5.6-luna-20260801",       # nome com sufixo de versao
            tokens=(1_000_000, 100_000)), PRECOS)
        self.assertAlmostEqual(gpt.custo_usd, 0.20 + 0.12)
        self.assertEqual(gpt.custo, "~US$ 0.3200")
        outro = cmp.linha_de(experimento(self.raiz, "outro", "1", provedor="openrouter",
                                         modelo="empresa/modelo-x"), PRECOS)
        self.assertEqual(outro.custo, "?")
        sem_rede = cmp.linha_de(experimento(self.raiz, "sem", "1", provedor="openrouter",
                                            modelo="openai/gpt-5.6-luna"), None)
        self.assertEqual(sem_rede.custo, "?")

    def test_tabelas_texto_e_markdown(self):
        linhas = [cmp.linha_de(experimento(self.raiz, "local", "1"), PRECOS),
                  cmp.linha_de(experimento(self.raiz, "gpt", "1", provedor="openrouter",
                                           modelo="openai/gpt-5.6-luna", exemplo="cpus/x"),
                               PRECOS)]
        texto = cmp.tabela_texto(linhas, precos_ok=True)
        self.assertIn("experimento", texto.splitlines()[0])
        self.assertIn("qwen2.5-coder:14b (local)", texto)
        self.assertIn("openai/gpt-5.6-luna (openrouter) +exemplo", texto)
        descrita = cmp.linha_de(experimento(self.raiz, "descrita", "1",
                                            descricao="reset sincrono"), PRECOS)
        self.assertIn("qwen2.5-coder:14b (local) +descricao",
                      cmp.tabela_texto([descrita], precos_ok=True))
        self.assertIn("custo: ESTIMATIVA", texto)
        md = cmp.tabela_markdown(linhas, precos_ok=False)
        self.assertIn("| experimento | modelo |", md)
        self.assertIn("|---|", md)
        self.assertIn("preco do OpenRouter indisponivel", md)

    def test_comando_comparar(self):
        experimento(self.raiz, "local", "1")
        md = self.raiz / "saida" / "COMPARACAO.md"
        saida = io.StringIO()
        with redirect_stdout(saida):
            codigo = main(["comparar", str(self.raiz), "--sem-rede", "--markdown", str(md)])
        self.assertEqual(codigo, 0)
        self.assertIn("APROVADO", saida.getvalue())
        self.assertTrue(md.read_text(encoding="utf-8").startswith("# Comparacao de experimentos"))
        vazio = self.raiz / "vazio"
        vazio.mkdir()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(["comparar", str(vazio), "--sem-rede"]), 1)


class TestPastaDoExperimento(unittest.TestCase):

    def test_nome_sem_diretorio_vai_para_experimentos(self):
        self.assertEqual(resolver_pasta("ia_mono"), (REPO_ROOT / "experimentos" / "ia_mono").resolve())
        absoluto = (REPO_ROOT / "entregas" / "x").resolve()
        self.assertEqual(resolver_pasta(str(absoluto)), absoluto)


if __name__ == "__main__":
    unittest.main()
