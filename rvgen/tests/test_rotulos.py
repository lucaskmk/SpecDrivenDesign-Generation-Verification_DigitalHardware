#!/usr/bin/env python3
"""Testes do verificador de rótulos (`rvgen/rotulos.py`). Sem IA nem GHDL."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rvgen import rotulos as rot
from rvgen.config import REPO_ROOT

CATALOGO = """# Rotulos
## FG-ALU — alu
### FC-ADD — soma
- CK-ADD-BASICO: soma
- CK-ADD-WRAP: 32 bits
## FG-RV32M — M [RV32M]
### FC-DIV — div
- CK-DIV-ZERO: divisor zero
- CK-DIV-OVERFLOW: overflow
"""

CONTRATO = """## Timing
x
## Labels
- CK-ADD-BASICO
- CK-DIV-ZERO
## Test strategy
y
"""


class TestCatalogo(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.arq = Path(self.tmp.name) / "rotulos.md"
        self.arq.write_text(CATALOGO, encoding="utf-8")
        self.cat = rot.carregar(self.arq)

    def tearDown(self):
        self.tmp.cleanup()

    def test_isa_filtra_o_m(self):
        self.assertEqual(self.cat.cks("rv32i"), {"CK-ADD-BASICO", "CK-ADD-WRAP"})
        self.assertEqual(len(self.cat.cks("rv32im")), 4)
        self.assertNotIn("CK-DIV-ZERO", self.cat.texto_para_prompt("rv32i"))
        self.assertIn("FC-DIV", self.cat.texto_para_prompt("rv32im"))

    def test_catalogo_malformado(self):
        self.arq.write_text("- CK-SOLTO: sem FC\n", encoding="utf-8")
        with self.assertRaises(rot.ErroRotulos):
            rot.carregar(self.arq)
        self.arq.write_text(CATALOGO + "- CK-ADD-WRAP: repetido\n", encoding="utf-8")
        with self.assertRaisesRegex(rot.ErroRotulos, "repetido"):
            rot.carregar(self.arq)
        with self.assertRaises(rot.ErroRotulos):
            rot.carregar(Path(self.tmp.name) / "nao_existe.md")

    def test_contrato(self):
        self.assertEqual(rot.ck_do_contrato(CONTRATO), {"CK-ADD-BASICO", "CK-DIV-ZERO"})
        self.assertEqual(rot.problemas_contrato(CONTRATO, self.cat, "rv32im"), [])
        # CK do M num contrato RV32I e rotulo inventado: recusados
        erros = rot.problemas_contrato(CONTRATO.replace("CK-ADD-BASICO", "CK-ADD-INVENTADO"),
                                       self.cat, "rv32i")
        self.assertTrue(any("CK-ADD-INVENTADO" in e and "CK-DIV-ZERO" in e for e in erros), erros)
        self.assertEqual(rot.problemas_contrato("## Timing\nx\n", self.cat, "rv32i"),
                         ["missing `## Labels` section"])
        self.assertNotIn("## Labels", rot.sem_secao_labels(CONTRATO))
        self.assertIn("## Test strategy", rot.sem_secao_labels(CONTRATO))

    def test_teste(self):
        bloco = {"CK-ADD-BASICO", "CK-DIV-ZERO"}
        ok = "# CK: CK-DIV-ZERO\nimport cocotb\n"
        self.assertEqual(rot.ck_do_teste(ok), {"CK-DIV-ZERO"})
        self.assertEqual(rot.problemas_teste(ok, bloco, self.cat, "rv32im"), [])
        self.assertTrue(rot.problemas_teste("import cocotb\n", bloco, self.cat, "rv32im"))
        self.assertEqual(rot.problemas_teste("import cocotb\n", bloco, self.cat, "rv32im",
                                             obrigatorio=False), [])
        fora = rot.problemas_teste("# CK: CK-ADD-WRAP, CK-NOVO\n", bloco, self.cat, "rv32im")
        self.assertTrue(any("CK-NOVO" in e for e in fora))
        self.assertTrue(any("CK-ADD-WRAP" in e and "Labels" in e for e in fora))
        # rotulo citado so no corpo do teste (nao no comentario # CK:) nao conta
        self.assertEqual(rot.ck_do_teste("x = 'CK-ADD-WRAP'\n"), set())

    def test_cobertura(self):
        sessao = Path(self.tmp.name) / "sessao"
        (sessao / "component_specs").mkdir(parents=True)
        (sessao / "testes").mkdir()
        (sessao / "component_specs" / "alu.comp_spec.txt").write_text(CONTRATO, encoding="utf-8")
        (sessao / "testes" / "test_alu.py").write_text("# CK: CK-ADD-BASICO\n", encoding="utf-8")
        c = rot.gravar_cobertura(sessao, ["alu"], self.cat, "rv32im")
        self.assertEqual(c["por_bloco"]["alu"]["cobertos"], ["CK-ADD-BASICO"])
        self.assertEqual(c["por_bloco"]["alu"]["sem_teste"], ["CK-DIV-ZERO"])
        self.assertEqual(c["por_bloco"]["alu"]["cobertura"], 0.5)
        self.assertEqual(c["sem_dono"], ["CK-ADD-WRAP", "CK-DIV-OVERFLOW"])
        self.assertEqual(c["cobertura_cpu"], 0.25)
        self.assertTrue((sessao / "rotulos_cobertura.json").is_file())


class TestCatalogoVersionado(unittest.TestCase):

    def test_specs_rotulos_md(self):
        cat = rot.carregar(REPO_ROOT / "specs" / "rotulos.md")
        self.assertEqual(len(cat.cks("rv32i")), 36)
        self.assertEqual(len(cat.cks("rv32im")) - len(cat.cks("rv32i")), 14)
        self.assertIn("CK-DIV-OVERFLOW", cat.cks("rv32im"))


if __name__ == "__main__":
    unittest.main()
