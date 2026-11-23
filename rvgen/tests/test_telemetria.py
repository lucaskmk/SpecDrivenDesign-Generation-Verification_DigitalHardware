#!/usr/bin/env python3
"""Testes do `rvgen telemetria`: soma por grupo de fases a partir do
`sessao.jsonl`. Nada aqui roda modelo, GHDL ou rede."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from rvgen import telemetria as tel
from rvgen.__main__ import main
from rvgen.config import REPO_ROOT


def llm(fase, entrada=100, saida=10, segundos=6.0, **extra):
    return {"evento": "llm", "fase": fase, "provedor": "openrouter",
            "modelo": "openai/gpt-6-luna", "tokens_entrada": entrada,
            "tokens_saida": saida, "segundos": segundos, **extra}


def sessao(raiz: Path, nome: str, eventos: list[dict], sid="20261120-100000") -> Path:
    s = raiz / nome / ".rvgen" / f"sessao-{sid}"
    s.mkdir(parents=True)
    (s / "sessao.jsonl").write_text(
        "\n".join(json.dumps(e) for e in eventos) + "\n", encoding="utf-8")
    return s


EVENTOS = [
    {"evento": "inicio", "modelo": "openai/gpt-6-luna", "provedor": "openrouter"},
    llm("instrucoes"), llm("decomposicao"),
    {"evento": "plano_evolucao_invalido", "motivo": "x"},
    llm("especificacao_componente"),
    {"evento": "especificacao_reprovada", "bloco": "alu", "tentativa": 1},
    llm("revisao_semantica_especificacao"),
    llm("escrita", entrada=1000, saida=200, segundos=60.0),
    llm("testbench"), llm("caso_publico_isolado", repeticoes_rede=2),
    {"evento": "teste_componente", "bloco": "alu", "passou": False, "segundos": 30.0},
    {"evento": "candidato_lote_executado", "bloco": "alu", "passou": True, "segundos": 30.0},
    {"evento": "candidato_lote_rejeitado", "bloco": "alu"},
    {"evento": "plano_teste_rejeitado", "bloco": "alu"},
    {"evento": "triagem_componente", "bloco": "alu", "causa": "testbench"},
    llm("triagem_componente"), llm("correcao_testbench"),
    {"evento": "llm_erro", "fase": "escrita", "erro": "HTTP 502"},
    {"evento": "spec-riscv-test", "rotulo": "linha-de-base", "placar": "40/40 casos",
     "segundos": 60.0},
    {"evento": "spec-riscv-test", "rotulo": "suite", "placar": "45/48 casos", "segundos": 120.0},
    llm("escolha"), llm("correcao"),
    {"evento": "spec-riscv-test", "rotulo": "suite", "placar": "nao compilou", "segundos": 0},
    llm("fase_que_nao_existe"),
    {"evento": "fim", "placar": "48/48 casos"},
]


class TestTelemetria(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.raiz = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_soma_por_grupo(self):
        t = tel.telemetria_de(sessao(self.raiz, "x", EVENTOS))
        g = t.grupos
        self.assertEqual((g["planejamento"].chamadas, g["planejamento"].recusas_validador), (2, 1))
        self.assertEqual((g["contratos"].chamadas, g["contratos"].recusas_revisor), (2, 1))
        self.assertEqual((g["vhdl"].chamadas, g["vhdl"].tokens_entrada,
                          g["vhdl"].tokens_saida, g["vhdl"].erros_provedor), (1, 1000, 200, 1))
        self.assertAlmostEqual(g["vhdl"].segundos_modelo, 60.0)
        self.assertEqual((g["testes"].chamadas, g["testes"].falhas,
                          g["testes"].recusas_validador, g["testes"].repeticoes_rede), (2, 1, 2, 2))
        self.assertAlmostEqual(g["testes"].segundos_simulacao, 60.0)
        self.assertEqual(g["correcao"].chamadas, 2)
        # juiz: 3 programas reprovados + 1 rodada que nem compilou
        self.assertEqual((g["juiz"].chamadas, g["juiz"].falhas), (2, 4))
        self.assertAlmostEqual(g["juiz"].segundos_simulacao, 120.0)
        self.assertEqual((g["linha de base"].falhas, g["linha de base"].segundos_simulacao), (0, 60.0))
        self.assertEqual(g["outros"].chamadas, 1)
        self.assertEqual(t.total.chamadas, 12)
        self.assertEqual(t.placar, "48/48 casos")
        self.assertEqual(t.triagem["testbench"], 1)
        self.assertTrue(t.repeticoes_registradas)
        self.assertEqual(t.fases["caso_publico_isolado"].chamadas, 1)

    def test_sessao_antiga_sem_repeticoes_e_parada_no_teto(self):
        eventos = [llm("escrita"), {"evento": "limite_atingido", "fase": "testbench"},
                   {"evento": "retomada"}, {"evento": "inicio"}]
        t = tel.telemetria_de(sessao(self.raiz, "y", eventos))
        self.assertFalse(t.repeticoes_registradas)
        self.assertTrue(t.parou_no_teto)
        self.assertEqual((t.placar, t.execucoes), ("-", 2))
        texto = tel.tabela_texto([t], precos_ok=False)
        self.assertIn("parou no teto", texto)
        self.assertIn("2 execucoes", texto)

    def test_custo_e_estimativa_por_grupo(self):
        precos = {"openai/gpt-6-luna": (0.10e-6, 0.50e-6)}
        t = tel.telemetria_de(sessao(self.raiz, "z", [llm("escrita", 1_000_000, 100_000)]), precos)
        self.assertAlmostEqual(t.grupos["vhdl"].custo_usd, 0.15)
        self.assertIn("US$ 0.150", tel.tabela_texto([t], precos_ok=True))
        sem = tel.telemetria_de(sessao(self.raiz, "w", [llm("escrita")]))
        self.assertIsNone(sem.total.custo_usd)

    def test_sessoes_inclui_interrompidas_e_a_mais_recente(self):
        sessao(self.raiz, "a", [llm("escrita")], sid="20261120-100000")
        sessao(self.raiz, "a", [llm("escrita")], sid="20261121-100000")
        achadas = tel.sessoes([self.raiz])
        self.assertEqual([s.name for s in achadas], ["sessao-20261121-100000"])
        self.assertEqual(len(tel.sessoes([self.raiz], todas=True)), 2)

    def test_markdown_e_resumo_por_experimento(self):
        a = tel.telemetria_de(sessao(self.raiz, "a", EVENTOS))
        b = tel.telemetria_de(sessao(self.raiz, "b", [llm("escrita")]))
        md = tel.tabela_markdown([a, b], precos_ok=False)
        self.assertIn("## Chamadas por grupo", md)
        self.assertIn("| a | openai/gpt-6-luna |", md)
        self.assertIn("## b", md)
        detalhado = tel.tabela_texto([a], precos_ok=False, detalhado=True)
        self.assertIn("caso_publico_isolado", detalhado)

    def test_cli_grava_markdown(self):
        sessao(self.raiz, "a", EVENTOS)
        destino = self.raiz / "t.md"
        with redirect_stdout(io.StringIO()) as out:
            codigo = main(["telemetria", str(self.raiz / "a"), "--sem-rede",
                           "--markdown", str(destino)])
        self.assertEqual(codigo, 0)
        self.assertIn("TOTAL", out.getvalue())
        self.assertIn("# Telemetria por fase", destino.read_text(encoding="utf-8"))

    def test_fases_do_codigo_tem_grupo(self):
        """Toda fase passada a `_chamar` no gerador cai num grupo conhecido."""
        import re
        fontes = (REPO_ROOT / "rvgen" / "agente.py").read_text(encoding="utf-8")
        fontes += (REPO_ROOT / "rvgen" / "evolucao.py").read_text(encoding="utf-8")
        fases = set(re.findall(r'_chamar\(\s*"([a-z_]+)"', fontes))
        self.assertTrue(fases)
        self.assertEqual(fases - set(tel.FASE_PARA_GRUPO), set())


class TestExperimentoVersionado(unittest.TestCase):
    """Âncora: os totais da sessão aprovada `luna6_prof_3` (artigo, seção 4.2)."""

    def test_luna6_prof_3(self):
        pasta = REPO_ROOT / "experimentos" / "luna6_prof_3"
        if not pasta.is_dir():
            self.skipTest("experimento nao versionado nesta copia")
        t = tel.telemetria_de(tel.sessoes([pasta])[0])
        self.assertEqual((t.total.chamadas, t.total.tokens_entrada, t.total.tokens_saida),
                         (78, 743978, 124821))
        self.assertEqual(t.grupos["testes"].chamadas, 49)
        self.assertEqual(t.execucoes, 4)


if __name__ == "__main__":
    unittest.main()
