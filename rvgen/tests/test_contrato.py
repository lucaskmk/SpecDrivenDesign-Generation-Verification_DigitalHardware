#!/usr/bin/env python3
"""Testes do contrato dos tipos e do `cpu.toml` deterministico.

REQ: FR-RV-47 (tipos e ISAs aceitos; manifesto que o rvverify aceita).

O juiz do manifesto e o proprio `rvverify.manifest`: se o leitor do
validador recusar o `cpu.toml` gerado, o teste falha -- nao existe uma
segunda definicao de "manifesto valido" aqui.
"""

from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from rvgen import contrato as ct
from rvverify.manifest import load_manifest


class TestTipos(unittest.TestCase):

    def test_recusa_o_que_o_rvverify_nao_julga(self):
        with self.assertRaisesRegex(ct.ErroContrato, "rv32i, rv32im"):
            ct.validar("monociclo", "rv32imc")
        with self.assertRaisesRegex(ct.ErroContrato, "monociclo, multiciclo, pipeline"):
            ct.validar("superescalar", "rv32i")
        self.assertIs(ct.validar("pipeline", "rv32im"), ct.TIPOS["pipeline"])

    def test_todo_tipo_termina_no_top_e_nao_reusa_nome_fornecido(self):
        for tipo in ct.TIPOS.values():
            nomes = [b.name for b in tipo.blocos]
            self.assertEqual(nomes[-1], ct.TOP, tipo.nome)
            self.assertEqual(len(nomes), len(set(nomes)), tipo.nome)
            self.assertFalse(set(nomes) & ct.ENTIDADES_RESERVADAS, tipo.nome)


class TestManifesto(unittest.TestCase):

    def test_cpu_toml_aceito_pelo_rvverify_em_todo_tipo_e_isa(self):
        for tipo in ct.TIPOS.values():
            for isa in ct.ISAS:
                with self.subTest(tipo=tipo.nome, isa=isa), \
                        tempfile.TemporaryDirectory() as d:
                    pasta = Path(d) / "gerada"
                    (pasta / "src").mkdir(parents=True)
                    arquivos = [f"src/{b.name}.vhd" for b in tipo.blocos]
                    for a in arquivos:
                        (pasta / a).write_text("-- vazio\n", encoding="utf-8")
                    texto = ct.renderizar_cpu_toml("gerada", pasta, tipo, isa, arquivos)
                    (pasta / "cpu.toml").write_text(texto, encoding="utf-8")

                    m = load_manifest(pasta)
                    fontes = m.source_paths()          # todas existem
                    self.assertEqual(len(fontes), len(ct.FORNECIDOS) + len(arquivos))
                    self.assertEqual(fontes[0].name, "cpu_package.vhd")
                    self.assertEqual(fontes[-1].name, f"{ct.TOP}.vhd")
                    self.assertEqual(m.design.top, ct.TOP)
                    self.assertEqual(m.design.rv32m_generic,
                                     "RV32M_ENABLE" if isa == "rv32im" else None)
                    self.assertEqual(m.halt.mode, tipo.halt["mode"])
                    self.assertNotEqual(m.halt.mode, "fixed_cycles")
                    self.assertEqual(m.observe.ram, "data_memory.data_ram.memory")
                    self.assertEqual(m.observe.registers, "register_file.registers")
                    self.assertTrue(m.program.loadable)
                    # caminhos POSIX: o mesmo manifesto vale no Docker
                    self.assertNotIn("\\", "".join(tomllib.loads(texto)["design"]["sources"]))

    def test_pipeline_declara_as_metricas_de_cpi(self):
        m = ct.TIPOS["pipeline"]
        self.assertEqual(m.halt["mode"], "commit_pc")
        self.assertEqual(set(m.metrics), {"stall", "flush_d", "flush_f", "m_dispatch"})


class TestPrompt(unittest.TestCase):

    def test_interfaces_vem_dos_arquivos_reais(self):
        texto = ct.interfaces_fornecidas()
        for trecho in ("entity instruction_memory is", "entity data_memory is",
                       "entity mul_div_unit is", "ALU_OP_TYPE_REMU",
                       "MEM_ACCESS_WIDTH_t", "DATA_RAM_BASE_ADDRESS"):
            self.assertIn(trecho, texto)
        # a constante com o programa embutido nao vai para o prompt
        self.assertNotIn("INSTRUCTION_MEMORY_CONTENT :", texto)

    def test_contrato_fixa_nomes_e_extensao_por_isa(self):
        tipo = ct.TIPOS["pipeline"]
        com_m = ct.texto_do_contrato(tipo, "rv32im")
        sem_m = ct.texto_do_contrato(tipo, "rv32i")
        for nome in ("`jump_e`", "`stall_pc`", "instance label `register_file`",
                     "entity cpu_top is"):
            self.assertIn(nome, com_m)
        self.assertIn("if RV32M_ENABLE generate", com_m)
        self.assertIn("RV32M is NOT required", sem_m)


if __name__ == "__main__":
    unittest.main()
