#!/usr/bin/env python3
"""Testes do contrato inferido de cpu.md e do `cpu.toml` deterministico.

REQ: FR-RV-47 (ISA aceita; manifesto que o rvverify aceita).

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


class TestConfiguracao(unittest.TestCase):

    def test_recusa_o_que_o_rvverify_nao_julga(self):
        with self.assertRaisesRegex(ct.ErroContrato, "rv32i, rv32im"):
            ct.validar_isa("rv32imc")
        ct.validar_isa("rv32im")

    def test_infere_configuracao_do_texto_em_markdown(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cpu.md"
            p.write_text("# CPU\n\nEsta CPU usa RV32IM e uma arquitetura single cycle.\n",
                         encoding="utf-8")
            self.assertEqual(ct.ler_configuracao_cpu(p),
                              {"microarquitetura": "monociclo", "isa": "rv32im", "descricao": None})

    def test_rv32m_nao_e_fonte_fornecida(self):
        self.assertNotIn("mul_div_unit.vhd", ct.FORNECIDOS)
        self.assertNotIn("mul_div_unit", ct.ENTIDADES_RESERVADAS)

class TestManifesto(unittest.TestCase):

    def test_cpu_toml_aceito_pelo_rvverify_em_cada_isa(self):
        for isa in ct.ISAS:
            with self.subTest(isa=isa), tempfile.TemporaryDirectory() as d:
                    pasta = Path(d) / "gerada"
                    (pasta / "src").mkdir(parents=True)
                    arquivos = ["src/alu.vhd", "src/cpu.vhd"]
                    for a in arquivos:
                        (pasta / a).write_text("-- vazio\n", encoding="utf-8")
                    texto = ct.renderizar_cpu_toml("gerada", pasta, isa, arquivos)
                    (pasta / "cpu.toml").write_text(texto, encoding="utf-8")

                    m = load_manifest(pasta)
                    fontes = m.source_paths()          # todas existem
                    self.assertEqual(len(fontes), len(arquivos))
                    self.assertEqual(fontes[0].name, Path(arquivos[0]).name)
                    self.assertEqual(fontes[-1].name, f"{ct.TOP}.vhd")
                    self.assertEqual(m.design.top, ct.TOP)
                    self.assertEqual(m.design.rv32m_generic,
                                     "RV32M_ENABLE" if isa == "rv32im" else None)
                    self.assertEqual(m.halt.mode, "fetch_pc")
                    self.assertNotEqual(m.halt.mode, "fixed_cycles")
                    self.assertEqual(m.observe.ram, "virtual")
                    self.assertIsNone(m.observe.registers)
                    self.assertTrue(m.program.loadable)
                    # caminhos POSIX: o mesmo manifesto vale no Docker
                    self.assertNotIn("\\", "".join(tomllib.loads(texto)["design"]["sources"]))

TOP_BOM = """entity cpu is
port(clk : in std_logic; rst : in std_logic; instr_addr : out std_logic_vector(31 downto 0);
instr_data : in std_logic_vector(31 downto 0); data_addr : out std_logic_vector(31 downto 0);
data_write : out std_logic; data_width : out std_logic_vector(1 downto 0);
data_write_data : out std_logic_vector(31 downto 0); data_read_data : in std_logic_vector(31 downto 0));
end cpu; architecture rtl of cpu is begin end rtl;"""


class TestChecagemDoContrato(unittest.TestCase):
    """`verificar_contrato`: o que o GHDL e o testbench reclamariam depois."""

    def _avisos(self, top):
        return [m for _, m in ct.verificar_contrato({"src/cpu.vhd": top})]

    def test_top_que_cumpre_o_contrato_nao_gera_aviso(self):
        self.assertEqual(self._avisos(TOP_BOM), [])

    def test_o_erro_real_da_trv_9_8(self):
        avisos = self._avisos(TOP_BOM.replace("data_write :", "write_enable :"))
        self.assertIn("cpu must declare the port `data_write`.", avisos)

    def test_generic_sinal_e_registers_ausentes(self):
        avisos = self._avisos(TOP_BOM.replace("data_width :", "width :"))
        self.assertIn("cpu must declare the port `data_width`.", avisos)

    def test_comentario_nao_conta_como_declaracao(self):
        top = TOP_BOM.replace("data_addr :", "-- data_addr :\naddr :")
        self.assertIn("cpu must declare the port `data_addr`.", self._avisos(top))

    def test_zero_avisos_nas_cpus_de_referencia(self):
        self.assertEqual(self._avisos(TOP_BOM), [])


class TestPrompt(unittest.TestCase):

    def test_interfaces_vem_dos_arquivos_reais(self):
        texto = ct.interfaces_fornecidas()
        for trecho in ("entity instruction_memory is", "entity data_memory is",
                       "ALU_OP_TYPE_REMU",
                       "MEM_ACCESS_WIDTH_t", "DATA_RAM_BASE_ADDRESS"):
            self.assertIn(trecho, texto)
        self.assertNotIn("entity mul_div_unit is", texto)
        # a constante com o programa embutido nao vai para o prompt
        self.assertNotIn("INSTRUCTION_MEMORY_CONTENT :", texto)

    def test_contrato_fixa_nomes_e_extensao_por_isa(self):
        com_m = ct.texto_do_contrato("pipeline", "rv32im")
        sem_m = ct.texto_do_contrato("pipeline", "rv32i")
        for nome in ("entity cpu is", "instr_addr", "data_read_data"):
            self.assertIn(nome, com_m)
        self.assertIn("Implement these operations in generated VHDL", com_m)
        self.assertIn("RV32M is NOT required", sem_m)
        self.assertIn("RV32I — referência de implementação", com_m)
        self.assertIn("I = sext(instr[31:20])", com_m)
        self.assertIn("### Formatos de instrução", com_m)
        self.assertIn("| B-type (variante de S) |", com_m)
        self.assertIn("| J-type (variante de U) |", com_m)
        self.assertIn("### Mapeamento de bits dos imediatos", com_m)
        self.assertIn("`inst[7]`", com_m)
        self.assertIn("`instr[30]` é `funct7(5)`", com_m)
        self.assertIn("| SLTU | `0x3` | `0x00` |", com_m)
        self.assertIn("| AND | `0x7` | `0x00` |", com_m)

    def test_regras_de_testes_sao_uma_especificacao_separada(self):
        regras = ct.texto_de_testes()
        self.assertIn("um único", regras)
        self.assertIn("reset síncrono", regras)
        self.assertIn("cocotb.result.TestFailure", regras)
        self.assertIn("Não enumere registradores", regras)
        self.assertIn("valores esperados e exemplos em hexadecimal", regras)
        self.assertIn("Ambiente externo para uma interface de CPU", regras)
        self.assertIn("Não instancie ROM, RAM", regras)


if __name__ == "__main__":
    unittest.main()
