#!/usr/bin/env python3
"""Testes do contrato inferido de cpu.md e do `cpu.toml` deterministico.

Confere a ISA aceita e o manifesto que o rvverify aceita.

O juiz do manifesto e o proprio `rvverify.manifest`: se o leitor do
validador recusar o `cpu.toml` gerado, o teste falha -- nao existe uma
segunda definicao de "manifesto valido" aqui.
"""

from __future__ import annotations

import os
import shutil
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
                    # o cabecalho nao cita requisitos que as specs nao tem mais
                    self.assertTrue(texto.startswith("# Manifesto gerado por rvgen:"))
                    self.assertNotIn("FR-RV", texto)
                    self.assertNotIn("REQ:", texto)

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

    def test_prompt_nao_manda_declarar_generic_nem_cita_pacote_antigo(self):
        # specs/cpu.md exige a entidade `cpu` exata, sem generics, e o
        # spec-riscv-test recusa uma entidade com generic: o prompt nao pode
        # mandar o modelo declarar RV32M_ENABLE, nem falar em rodar a CPU duas vezes.
        for isa in ct.ISAS:
            with self.subTest(isa=isa):
                texto = ct.texto_do_contrato("single cycle", isa)
                self.assertNotIn("RV32M_ENABLE", texto)
                self.assertNotIn("ALU_OP_TYPE", texto)
                self.assertNotIn("same CPU twice", texto)
                self.assertIn("no generics", texto)

    def test_regras_de_vhdl_nao_exigem_comentario_req(self):
        # as specs nao pedem mais comentario de rastreabilidade nos VHDL
        self.assertNotIn("-- REQ:", ct.texto_do_contrato("single cycle", "rv32i"))

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

    def test_referencia_do_m_so_entra_com_rv32im(self):
        # I e M sao arquivos separados: RV32I le so riscv-rv32i.md; RV32IM le os dois
        com_m = ct.texto_do_contrato("single cycle", "rv32im")
        sem_m = ct.texto_do_contrato("single cycle", "rv32i")
        self.assertIn("# RV32M Implementation Reference", com_m)
        self.assertIn("| MULHSU | `0x2` | `0x01` |", com_m)
        self.assertIn("| divisor = 0 |", com_m)
        self.assertNotIn("RV32M Implementation Reference", sem_m)
        self.assertNotIn("MULHSU |", sem_m)
        self.assertEqual(ct.arquivos_da_isa("rv32i"), ("riscv-rv32i.md",))
        self.assertEqual(ct.arquivos_da_isa("rv32im"), ("riscv-rv32i.md", "riscv-rv32m.md"))

    def test_rv32im_sem_referencia_do_m_e_erro_claro(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = Path(d)
            for nome in ("cpu.md", "vhdl.md", "riscv-rv32i.md"):
                shutil.copy(ct.SPECS_DIR / nome, pasta / nome)
            self.assertIn("RV32I Implementation", ct.texto_do_contrato("single cycle", "rv32i", pasta))
            with self.assertRaisesRegex(ct.ErroContrato, "RV32IM.*riscv-rv32m.md"):
                ct.texto_do_contrato("single cycle", "rv32im", pasta)

    def test_exemplos_do_m_batem_com_a_aritmetica(self):
        # confere a tabela "Exemplos para conferir" de riscv-rv32m.md
        def s(x):
            return x - (1 << 32) if x >> 31 else x

        def trunc(a, b):
            q = abs(a) // abs(b)
            return q if (a < 0) == (b < 0) else -q

        def m(op, a, b):
            if op == "MUL":
                return a * b
            if op == "MULH":
                return (s(a) * s(b)) >> 32
            if op == "MULHSU":
                return (s(a) * b) >> 32
            if op == "MULHU":
                return (a * b) >> 32
            if b == 0:
                return {"DIV": -1, "DIVU": -1, "REM": a, "REMU": a}[op]
            if op == "DIV":
                return -(1 << 31) if (s(a), s(b)) == (-(1 << 31), -1) else trunc(s(a), s(b))
            if op == "DIVU":
                return a // b
            if op == "REM":
                return 0 if (s(a), s(b)) == (-(1 << 31), -1) else s(a) - s(b) * trunc(s(a), s(b))
            return a % b

        texto = (ct.SPECS_DIR / "riscv-rv32m.md").read_text(encoding="utf-8")
        exemplos = texto.split("## Exemplos para conferir", 1)[1].split("##", 1)[0]
        linhas = [ln for ln in exemplos.splitlines() if ln.startswith("| ") and "0x" in ln]
        self.assertEqual(len(linhas), 12)
        for ln in linhas:
            op, a, b, rd = (c.strip() for c in ln.strip("|").split("|"))
            a, b, rd = (int(c.split("`")[1], 16) for c in (a, b, rd))
            with self.subTest(linha=ln):
                self.assertEqual(m(op, a, b) & 0xFFFFFFFF, rd)

    def test_numero_de_programas_bate_com_o_juiz(self):
        import importlib
        import sys
        raiz = str(ct.REPO_ROOT / "spec-riscv-test")
        if raiz not in sys.path:
            sys.path.insert(0, raiz)
        try:
            mod = importlib.import_module("spec_riscv_test.cli")
        except ImportError as e:  # dependencia do juiz ausente neste ambiente
            self.skipTest(f"spec_riscv_test.cli nao importa aqui: {e}")
        self.assertEqual({isa: len(p) for isa, p in mod.ISA_PROFILES.items()}, ct.PROGRAMAS_DO_JUIZ)
        self.assertIn("48 programas", ct.descrever_isa("rv32im"))
        self.assertIn("sem M", ct.descrever_isa("rv32i"))

    def test_regras_de_testes_sao_uma_especificacao_separada(self):
        regras = ct.texto_de_testes()
        self.assertIn("um único", regras)
        self.assertIn("reset síncrono", regras)
        self.assertIn("cocotb.result.TestFailure", regras)
        self.assertIn("Não enumere registradores", regras)
        self.assertIn("valores esperados e exemplos em hexadecimal", regras)
        self.assertIn("Ambiente externo para uma interface de CPU", regras)
        self.assertIn("Não instancie ROM, RAM", regras)


class TestPastaDeSpecs(unittest.TestCase):
    """RVGEN_SPECS_DIR troca a pasta de onde saem os .md do prompt."""

    def setUp(self):
        self._antes = os.environ.pop(ct.VAR_SPECS, None)

    def tearDown(self):
        os.environ.pop(ct.VAR_SPECS, None)
        if self._antes is not None:
            os.environ[ct.VAR_SPECS] = self._antes

    def _copia_alterada(self, destino: Path) -> Path:
        pasta = destino / "specs"
        pasta.mkdir()
        for arq in ("cpu.md", "vhdl.md", "riscv-rv32i.md", "testes.md"):
            shutil.copyfile(ct.SPECS_DIR / arq, pasta / arq)
        with open(pasta / "vhdl.md", "a", encoding="utf-8") as f:
            f.write("\nMARCA_DA_ITERACAO: regra extra.\n")
        with open(pasta / "testes.md", "a", encoding="utf-8") as f:
            f.write("\nMARCA_DE_TESTE\n")
        return pasta

    def test_sem_variavel_tudo_igual(self):
        self.assertEqual(ct.pasta_specs(), ct.SPECS_DIR)
        self.assertFalse(ct.pasta_specs_alterada())
        self.assertEqual(ct.texto_do_contrato("single cycle", "rv32i"),
                         ct.texto_do_contrato("single cycle", "rv32i", ct.SPECS_DIR))
        self.assertEqual(ct.ler_configuracao_cpu(), ct.ler_configuracao_cpu(ct.CPU_SPEC))
        self.assertEqual(ct.descrever_pasta_specs(), "specs")

    def test_variavel_absoluta_muda_o_prompt(self):
        original = ct.texto_do_contrato("single cycle", "rv32i")
        with tempfile.TemporaryDirectory() as d:
            pasta = self._copia_alterada(Path(d))
            os.environ[ct.VAR_SPECS] = str(pasta)
            self.assertEqual(ct.pasta_specs(), pasta.resolve())
            alterado = ct.texto_do_contrato("single cycle", "rv32i")
            self.assertIn("MARCA_DA_ITERACAO", alterado)
            self.assertIn("MARCA_DE_TESTE", ct.texto_de_testes())
            self.assertGreater(len(alterado), len(original))
            self.assertEqual(ct.ler_configuracao_cpu()["isa"],
                             ct.ler_configuracao_cpu(ct.CPU_SPEC)["isa"])
        self.assertNotIn("MARCA_DA_ITERACAO", original)

    def test_variavel_relativa_a_raiz(self):
        os.environ[ct.VAR_SPECS] = "specs"
        self.assertTrue(ct.pasta_specs_alterada())
        self.assertEqual(ct.pasta_specs(), ct.SPECS_DIR.resolve())
        self.assertEqual(ct.descrever_pasta_specs(), "specs")

    def test_pasta_explicita_ignora_a_variavel(self):
        with tempfile.TemporaryDirectory() as d:
            pasta = self._copia_alterada(Path(d))
            os.environ[ct.VAR_SPECS] = str(pasta)
            self.assertNotIn("MARCA_DA_ITERACAO",
                             ct.texto_do_contrato("single cycle", "rv32i", ct.SPECS_DIR))

    def test_pasta_inexistente_vira_erro_de_contrato(self):
        os.environ[ct.VAR_SPECS] = "pasta/que/nao/existe"
        with self.assertRaisesRegex(ct.ErroContrato,
                                    r"RVGEN_SPECS_DIR='pasta/que/nao/existe'.*nao existe"):
            ct.ler_configuracao_cpu()
        with self.assertRaises(ct.ErroContrato):
            ct.texto_de_testes()


if __name__ == "__main__":
    unittest.main()
