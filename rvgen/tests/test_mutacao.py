#!/usr/bin/env python3
"""Testes do `rvgen mutacao`: geração de mutantes (Python puro) e a conta do
mutation score com um executor falso. Nada aqui roda GHDL nem o juiz."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rvgen import mutacao as mut
from rvgen.executor import Execucao

VHDL = '''library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity bloco is
    port(
        a : in std_logic_vector(31 downto 0);   -- a = b nao e codigo
        b : in std_logic_vector(31 downto 0);
        y : out std_logic_vector(31 downto 0)
    );
end entity bloco;

architecture rtl of bloco is
    signal t : unsigned(31 downto 0);
begin
    process(a, b)
    begin
        if b = x"00000000" then          -- divisor zero
            y <= (others => '1');
        else
            y <= std_logic_vector(unsigned(a) / unsigned(b));
        end if;
    end process;
end architecture rtl;
'''


class TestGerarMutantes(unittest.TestCase):

    def setUp(self):
        self.ms = mut.gerar_mutantes(VHDL)

    def test_nao_muta_portas_declaracoes_nem_comentarios(self):
        linhas = {m.linha for m in self.ms}
        self.assertTrue(linhas)
        self.assertTrue(all(l >= 17 for l in linhas), linhas)   # so o corpo do processo
        self.assertFalse(any("divisor" in m.mutado for m in self.ms))

    def test_operadores_esperados(self):
        trocas = {(m.operador, m.original, m.mutado) for m in self.ms}
        self.assertIn(("relacional", "=", "/="), trocas)
        self.assertIn(("constante", 'x"00000000"', 'x"00000001"'), trocas)
        self.assertIn(("constante", 'x"00000000"', 'x"80000000"'), trocas)
        self.assertIn(("constante", "'1'", "'0'"), trocas)
        self.assertIn(("aritmetico", "/", " rem "), trocas)
        self.assertIn(("tipo", "unsigned(", "signed("), trocas)
        # `<=` de atribuicao e `=>` de agregado nunca viram relacional
        self.assertFalse(any(m.original in ("<=", "=>") for m in self.ms))

    def test_um_mutante_muda_uma_coisa_so(self):
        for m in self.ms:
            self.assertNotEqual(m.texto, VHDL)
            dif = [(a, b) for a, b in zip(VHDL.splitlines(), m.texto.splitlines()) if a != b]
            self.assertEqual(len(dif), 1, m)
            self.assertEqual(len(VHDL.splitlines()), len(m.texto.splitlines()))

    def test_deterministico(self):
        self.assertEqual([(m.id, m.texto) for m in self.ms],
                         [(m.id, m.texto) for m in mut.gerar_mutantes(VHDL)])

    def test_selecao_muda_bits(self):
        texto = VHDL.replace("y <= std_logic_vector(unsigned(a) / unsigned(b));",
                             "y <= std_logic_vector(t(31 downto 0));")
        sel = [m for m in mut.gerar_mutantes(texto) if m.operador == "selecao"]
        self.assertEqual([m.mutado for m in sel], ["(32 downto 1)"])


class ExecutorFalso:
    """Mata o mutante conforme o texto do VHDL copiado para a pasta."""

    def __init__(self, arquivo: str):
        self.arquivo = arquivo

    def _vhdl(self, pasta: Path) -> str:
        return (pasta / self.arquivo).read_text(encoding="utf-8")

    def rodar_componente(self, pasta, *, componente, teste, json_saida, workdir,
                         build_root, fontes=None, vcd=None, timeout=0):
        v = self._vhdl(pasta)
        if teste.name == "oraculo_cpu.py":       # oraculo no nivel da cpu: todas as fontes
            assert componente == "cpu" and len(fontes) == 2, (componente, fontes)
            rel = {"compilacao": {"ok": True}, "passed": "others => '0'" not in v}
            return Execucao([], 0, rel, "", 0.1, json_saida)
        if teste.name == "oraculo.py":           # referencia: so o bit de "others" importa
            rel = {"compilacao": {"ok": True}, "passed": "others => '0'" not in v}
            return Execucao([], 0, rel, "", 0.1, json_saida)
        compila = "rem" not in v                  # rem sobre unsigned: "nao compila"
        passou = compila and not (componente == "bloco" and "/=" in v) \
            and not (componente == "cpu" and "x\"00000001\"" in v)
        rel = {"compilacao": {"ok": compila}, "passed": passou, "detail": "x"}
        return Execucao([], 0, rel, "", 0.1, json_saida)

    def rodar(self, pasta, *, json_saida, workdir, build_root, casos=None, etapa="rv32i",
              timeout=0):
        v = self._vhdl(pasta)
        falhou = "/=" in v or 'x"80000000"' in v
        return Execucao([], 0, {"passed": 7 if falhou else 8, "executed": 8}, "", 0.1, json_saida)


class TestRodar(unittest.TestCase):

    def test_score_por_nivel(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu = Path(tmp) / "cpu_x"
            (cpu / "src").mkdir(parents=True)
            (cpu / "src" / "bloco.vhd").write_text(VHDL, encoding="utf-8")
            (cpu / "src" / "cpu.vhd").write_text("-- topo\n", encoding="utf-8")
            (cpu / "cpu.toml").write_text(
                '[design]\nname = "x"\ntop = "cpu"\nstd = "08"\n'
                'sources = ["src/bloco.vhd", "src/cpu.vhd"]\n', encoding="utf-8")
            sessao = cpu / ".rvgen" / "sessao-20261120-100000"
            (sessao / "testes").mkdir(parents=True)
            (sessao / "testes" / "test_bloco.py").write_text("# t\n", encoding="utf-8")
            (sessao / "testes" / "test_cpu.py").write_text("# t\n", encoding="utf-8")
            (sessao / "resultado.json").write_text(json.dumps({"veredito": "aprovado",
                                                               "isa": "rv32im"}))
            r = mut.rodar(cpu, "bloco", isa="rv32im", trabalho=Path(tmp) / "trab",
                          executor=ExecutorFalso("src/bloco.vhd"), paralelo=2,
                          relatar=lambda _: None)
        ms = mut.gerar_mutantes(VHDL)
        natimortos = sum(1 for m in ms if "rem" in m.mutado)
        self.assertEqual(r["natimortos"], natimortos)
        viaveis = len(ms) - natimortos
        n = r["por_nivel"]
        self.assertEqual(n["bloco"], {"mortos": 1, "viaveis": viaveis,
                                      "score": round(1 / viaveis, 3)})
        self.assertEqual(n["cpu"]["mortos"], 1)        # x"00000001"
        self.assertEqual(n["juiz"]["mortos"], 2)       # /= e x"80000000"
        so_juiz = {d["mutado"] for d in r["resultados"] if d["id"] in r["so_o_juiz_matou"]}
        self.assertEqual(so_juiz, {'x"80000000"'})
        so_comp = {d["mutado"] for d in r["resultados"] if d["id"] in r["so_componentes_mataram"]}
        self.assertEqual(so_comp, {'x"00000001"'})
        self.assertEqual(len(r["sobreviventes"]), viaveis - 3)
        self.assertIn("juiz", mut.resumo_texto(r))
        self.assertIn("| `cpu_x` | `bloco` |", mut.resumo_markdown([r]))

    def test_oraculo_separa_equivalentes_de_escapados(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu = Path(tmp) / "cpu_z"
            (cpu / "src").mkdir(parents=True)
            (cpu / "src" / "bloco.vhd").write_text(VHDL, encoding="utf-8")
            (cpu / "architecture.json").write_text(json.dumps(
                {"blocks": [{"name": "bloco", "file": "src/bloco.vhd"}]}))
            sessao = cpu / ".rvgen" / "sessao-1"
            (sessao / "testes").mkdir(parents=True)
            (sessao / "testes" / "test_bloco.py").write_text("# t\n", encoding="utf-8")
            (sessao / "resultado.json").write_text(json.dumps({"veredito": "aprovado"}))
            r = mut.rodar(cpu, "bloco", isa="rv32i", trabalho=Path(tmp) / "t",
                          executor=ExecutorFalso("src/bloco.vhd"), oraculo=Path("oraculo.py"),
                          relatar=lambda _: None)
        o = r["oraculo"]
        escaparam = {d["mutado"] for d in r["resultados"] if d["id"] in o["escaparam"]}
        self.assertEqual(escaparam, {"'0'"})
        self.assertEqual(len(o["equivalentes"]) + len(o["escaparam"]), len(r["sobreviventes"]))
        s = r["por_nivel_sem_equivalentes"]
        self.assertEqual(s["juiz"]["viaveis"], r["por_nivel"]["juiz"]["viaveis"] - len(o["equivalentes"]))
        self.assertIn("escaparam de todos", mut.resumo_texto(r))
        self.assertIn("| 1 |", mut.resumo_markdown([r]).splitlines()[-1][-6:])

    def test_oraculo_de_cpu_roda_na_entidade_cpu(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu = Path(tmp) / "cpu_w"
            (cpu / "src").mkdir(parents=True)
            (cpu / "src" / "bloco.vhd").write_text(VHDL, encoding="utf-8")
            (cpu / "src" / "cpu.vhd").write_text("-- topo\n", encoding="utf-8")
            (cpu / "cpu.toml").write_text(
                '[design]\nname = "w"\ntop = "cpu"\nstd = "08"\n'
                'sources = ["src/bloco.vhd", "src/cpu.vhd"]\n', encoding="utf-8")
            sessao = cpu / ".rvgen" / "sessao-1"
            (sessao / "testes").mkdir(parents=True)
            (sessao / "testes" / "test_bloco.py").write_text("# t\n", encoding="utf-8")
            (sessao / "resultado.json").write_text(json.dumps({"veredito": "aprovado"}))
            r = mut.rodar(cpu, "bloco", isa="rv32im", trabalho=Path(tmp) / "t",
                          executor=ExecutorFalso("src/bloco.vhd"),
                          oraculo=Path("oraculo_cpu.py"), relatar=lambda _: None)
        self.assertEqual(r["oraculo"]["componente"], "cpu")
        self.assertEqual(len(r["oraculo"]["escaparam"]), 1)

    def test_original_reprovado_invalida_a_medida(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu = Path(tmp) / "cpu_y"
            (cpu / "src").mkdir(parents=True)
            (cpu / "src" / "bloco.vhd").write_text(VHDL.replace(" = ", " /= "), encoding="utf-8")
            (cpu / "architecture.json").write_text(json.dumps(
                {"blocks": [{"name": "bloco", "file": "src/bloco.vhd"}]}))
            sessao = cpu / ".rvgen" / "sessao-1"
            (sessao / "testes").mkdir(parents=True)
            (sessao / "testes" / "test_bloco.py").write_text("# t\n", encoding="utf-8")
            (sessao / "resultado.json").write_text(json.dumps({"veredito": "aprovado"}))
            with self.assertRaisesRegex(RuntimeError, "original"):
                mut.rodar(cpu, "bloco", isa="rv32i", trabalho=Path(tmp) / "t",
                          executor=ExecutorFalso("src/bloco.vhd"), relatar=lambda _: None)


if __name__ == "__main__":
    unittest.main()
