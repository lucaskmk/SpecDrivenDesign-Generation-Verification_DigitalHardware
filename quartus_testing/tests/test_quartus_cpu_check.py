#!/usr/bin/env python3
"""Testes de quartus_testing/quartus_cpu_check.py -- sem Docker e sem Quartus.

Os parsers sao conferidos contra saida REAL do Quartus 25.1: os logs
versionados em implemetation_tests/opus_5_RISCVIM/fpga/quartus_output_*/
(nao cabe, nao roteia, compila) e os de fixtures/, capturados rodando a
propria ferramenta (erro de VHDL, clock que nao casa com porta) ou recortados
de um .fit.rpt real (a tabela de recursos, que nao e versionada). A execucao
inteira roda com um Docker falso que devolve esses mesmos arquivos.

    python -m pytest quartus_testing/tests
"""

from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from quartus_testing import quartus_cpu_check as q

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).resolve().parent / "fixtures"
OPUS = RAIZ / "implemetation_tests" / "opus_5_RISCVIM" / "fpga"


def ler(caminho: Path) -> str:
    return caminho.read_text(encoding="utf-8", errors="replace")


def escrever_cpu(pasta: Path, *, toml: str, vhdl: dict[str, str]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / "cpu.toml").write_text(toml, encoding="utf-8")
    for nome, texto in vhdl.items():
        (pasta / nome).parent.mkdir(parents=True, exist_ok=True)
        (pasta / nome).write_text(texto, encoding="utf-8")
    return pasta


TOML_MINIMO = """
[design]
name = "mini"
top  = "mini"
sources = ["src/mini.vhd"]

[clock]
signal = "clk"
period_ns = 20
"""

VHDL_SEM_SAIDA = """
-- port ( x : out bit ) num comentario nao conta
entity mini is
    port (clk : in std_logic;  -- saida : out std_logic
          rst : in std_logic);
end entity mini;
"""


class TestManifesto(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_cpu_de_referencia(self):
        cpu = q.carregar_cpu(RAIZ / "cpus" / "rv32i_pipeline")
        self.assertEqual((cpu.nome, cpu.top, cpu.clock, cpu.periodo_ns),
                         ("rv32i_pipeline", "CPU", "clk", 10.0))
        self.assertEqual(cpu.rv32m_generic, "RV32M_ENABLE")
        self.assertEqual(cpu.fontes[0].name, "cpu_package.vhd")     # ordem de analise
        self.assertEqual(cpu.fontes[-1].name, "CPU.vhd")
        self.assertTrue(all(f.is_file() for f in cpu.fontes))

    def test_fontes_fora_da_pasta_da_cpu(self):
        # o monociclo aponta para ../rv32i_pipeline/src, como toda entrega
        cpu = q.carregar_cpu(RAIZ / "cpus" / "rv32i_monociclo")
        self.assertEqual(cpu.fontes[0], (RAIZ / "cpus" / "rv32i_pipeline" / "src" / "cpu_package.vhd").resolve())

    def test_so_design_e_clock_bastam(self):
        # [observe], [halt] etc. sao do simulador: a sintese nao precisa deles
        cpu = q.carregar_cpu(escrever_cpu(self.tmp / "c", toml=TOML_MINIMO, vhdl={"src/mini.vhd": VHDL_SEM_SAIDA}))
        self.assertEqual(cpu.std, "08")
        self.assertIsNone(cpu.rv32m_generic)

    def test_erros_de_entrada(self):
        casos = {
            "sem cpu.toml": (None, "nao tem cpu.toml"),
            "sem clock": (TOML_MINIMO.split("[clock]")[0], r"\[clock\]"),
            "fonte inexistente": (TOML_MINIMO.replace("src/mini.vhd", "src/nao_existe.vhd"), "nao existem"),
            "std desconhecido": (TOML_MINIMO.replace('top  = "mini"', 'top = "mini"\nstd = "17"'), "std"),
            "periodo zero": (TOML_MINIMO.replace("period_ns = 20", "period_ns = 0"), "period_ns"),
        }
        for nome, (toml, msg) in casos.items():
            with self.subTest(nome):
                pasta = self.tmp / nome.replace(" ", "_")
                pasta.mkdir()
                (pasta / "src").mkdir()
                (pasta / "src" / "mini.vhd").write_text(VHDL_SEM_SAIDA)
                if toml is not None:
                    (pasta / "cpu.toml").write_text(toml)
                with self.assertRaisesRegex(q.ErroDeEntrada, msg):
                    q.carregar_cpu(pasta)


class TestTopTemSaida(unittest.TestCase):

    def test_cpus_do_repositorio(self):
        # as de referencia so tem clk/rst (o cocotb le por dentro); a opus
        # expoe dbg_* -- e por isso ela nunca precisou de noprune
        self.assertIs(q.carregar_cpu(RAIZ / "cpus" / "rv32i_pipeline").top_tem_saida, False)
        self.assertIs(q.carregar_cpu(RAIZ / "cpus" / "rv32i_monociclo").top_tem_saida, False)
        self.assertIs(q.carregar_cpu(RAIZ / "implemetation_tests" / "opus_5_RISCVIM").top_tem_saida, True)

    def test_comentario_nao_conta_e_entidade_ausente_e_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "a.vhd"
            f.write_text(VHDL_SEM_SAIDA)
            self.assertIs(q.top_tem_saida((f,), "mini"), False)
            self.assertIs(q.top_tem_saida((f,), "MINI"), False)          # VHDL ignora caixa
            self.assertIsNone(q.top_tem_saida((f,), "outra"))
            f.write_text(VHDL_SEM_SAIDA.replace("rst : in std_logic", "led : buffer std_logic"))
            self.assertIs(q.top_tem_saida((f,), "mini"), True)


class TestRevisoes(unittest.TestCase):

    def setUp(self):
        self.cpu = q.carregar_cpu(RAIZ / "cpus" / "rv32i_pipeline")

    def test_padrao_nao_mexe_em_generic(self):
        [rev] = q.revisoes_para(self.cpu, "padrao")
        self.assertEqual((rev.nome, rev.generics), ("padrao", {}))

    def test_ambas_poe_a_baseline_primeiro(self):
        revs = q.revisoes_para(self.cpu, "ambas")
        self.assertEqual([(r.nome, r.generics) for r in revs],
                         [("rv32i", {"RV32M_ENABLE": False}), ("rv32im", {"RV32M_ENABLE": True})])

    def test_sem_rv32m_generic_recusa(self):
        with tempfile.TemporaryDirectory() as tmp:
            cpu = q.carregar_cpu(escrever_cpu(Path(tmp), toml=TOML_MINIMO, vhdl={"src/mini.vhd": VHDL_SEM_SAIDA}))
        with self.assertRaisesRegex(q.ErroDeEntrada, "rv32m_generic"):
            q.revisoes_para(cpu, "rv32im")

    def test_familia_do_device(self):
        self.assertEqual(q.familia_do_device("5CEBA4F23C7"), "Cyclone V")
        self.assertEqual(q.familia_do_device("10m50daf484c7g"), "MAX 10")
        self.assertIsNone(q.familia_do_device("XC7A35T"))


class TestProjetoGerado(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self._tmp.name)
        self.cpu = q.carregar_cpu(RAIZ / "cpus" / "rv32i_monociclo")

    def tearDown(self):
        self._tmp.cleanup()

    def gerar(self, revisoes, **kw):
        opcoes = dict(device="5CEBA4F23C7", familia="Cyclone V", periodo_ns=10.0, roteamento_agressivo=False)
        opcoes.update(kw)
        return q.gerar_projeto(self.cpu, self.pasta, revisoes, **opcoes)

    def test_fontes_copiadas_na_ordem_e_iguais(self):
        proj = self.gerar(q.revisoes_para(self.cpu, "ambas"))
        comum = ler(self.pasta / "comum.tcl")
        arquivos = [l.split("src/")[1] for l in comum.splitlines() if "VHDL_FILE" in l]
        self.assertEqual(arquivos, [f.name for f in self.cpu.fontes])
        for nome, original in proj.fontes.items():
            self.assertEqual((self.pasta / "src" / nome).read_bytes(), (RAIZ / original).read_bytes())
        self.assertIn('set_global_assignment -name FAMILY "Cyclone V"', comum)
        self.assertIn("set_global_assignment -name DEVICE 5CEBA4F23C7", comum)
        self.assertIn("set_global_assignment -name TOP_LEVEL_ENTITY cpu_monocycle", comum)
        self.assertIn("VHDL_INPUT_VERSION VHDL_2008", comum)
        self.assertIn("SDC_FILE rv32i_monociclo.sdc", comum)
        self.assertNotIn("PRESERVE_FANOUT_FREE_NODE", comum)
        self.assertNotIn("FITTER_AGGRESSIVE_ROUTABILITY_OPTIMIZATION", comum)

    def test_sdc_e_revisoes(self):
        self.gerar(q.revisoes_para(self.cpu, "ambas"), periodo_ns=20.0)
        self.assertIn("create_clock -name {clk} -period 20.000 [get_ports {clk}]",
                      ler(self.pasta / "rv32i_monociclo.sdc"))
        qpf = ler(self.pasta / "rv32i_monociclo.qpf")
        self.assertLess(qpf.index('"rv32i"'), qpf.index('"rv32im"'))
        self.assertIn("set_parameter -name RV32M_ENABLE false", ler(self.pasta / "rv32i.qsf"))
        self.assertIn("set_parameter -name RV32M_ENABLE true", ler(self.pasta / "rv32im.qsf"))
        self.assertIn("SOURCE_TCL_SCRIPT_FILE comum.tcl", ler(self.pasta / "rv32im.qsf"))

    def test_opcoes_de_ferramenta(self):
        self.gerar(q.revisoes_para(self.cpu, "padrao"), roteamento_agressivo=True, preservar_logica=True)
        comum = ler(self.pasta / "comum.tcl")
        # a forma que funcionou de verdade: raiz, sem wildcard, instance assignment
        self.assertIn('set_instance_assignment -name PRESERVE_FANOUT_FREE_NODE ON -to "|"', comum)
        self.assertIn("FITTER_AGGRESSIVE_ROUTABILITY_OPTIMIZATION ALWAYS", comum)

    def test_generic_string_vazia_fica_no_default(self):
        rev = q.Revisao("padrao", {"ROM_INIT_FILE": "", "ROM_SIZE_WORDS": 256}, "x")
        proj = self.gerar([rev])
        qsf = ler(self.pasta / "padrao.qsf")
        self.assertNotIn("set_parameter -name ROM_INIT_FILE", qsf)
        self.assertIn("set_parameter -name ROM_SIZE_WORDS 256", qsf)
        self.assertEqual(proj.generics_ignorados, {"padrao": ["ROM_INIT_FILE"]})

    def test_nomes_de_fonte_repetidos_nao_se_sobrescrevem(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = escrever_cpu(Path(tmp) / "c", toml=TOML_MINIMO.replace(
                'sources = ["src/mini.vhd"]', 'sources = ["a/pkg.vhd", "b/pkg.vhd", "src/mini.vhd"]'),
                vhdl={"a/pkg.vhd": "-- a", "b/pkg.vhd": "-- b", "src/mini.vhd": VHDL_SEM_SAIDA})
            cpu = q.carregar_cpu(pasta)
            proj = q.gerar_projeto(cpu, Path(tmp) / "p", q.revisoes_para(cpu, "padrao"), device="5CEBA4F23C7",
                                   familia="Cyclone V", periodo_ns=20, roteamento_agressivo=False)
            self.assertEqual(list(proj.fontes), ["pkg.vhd", "01_pkg.vhd", "mini.vhd"])
            self.assertEqual(ler(Path(tmp) / "p" / "src" / "01_pkg.vhd"), "-- b")


class TestLogDeCompilacao(unittest.TestCase):

    def test_erro_de_vhdl(self):
        # capturado rodando a ferramenta sobre o monociclo com um sinal nao declarado
        c = q.parse_compile_log(ler(FIX / "compile_erro_sintese.log"),
                                {"mono_alu.vhd": "cpus/rv32i_monociclo/src/mono_alu.vhd"})
        self.assertFalse(c["compila"])
        self.assertEqual(c["etapa_que_falhou"], "Analysis & Synthesis")
        [erro] = c["erros"]                                   # o resto e eco de resumo
        self.assertEqual((erro["id"], erro["arquivo"], erro["linha"]),
                         ("10482", "cpus/rv32i_monociclo/src/mono_alu.vhd", 47))
        self.assertIn("sinal_que_nao_existe", erro["mensagem"])
        self.assertNotIn("/workspace/", erro["mensagem"])     # caminho do container traduzido
        self.assertEqual(q.classificar_falha(c, None)[0], "erro_de_sintese")

    def test_nao_cabe(self):
        c = q.parse_compile_log(ler(OPUS / "quartus_output_rv32i" / "compilation" / "compile.log"))
        self.assertEqual(c["etapa_que_falhou"], "Fitter")
        self.assertEqual([e["id"] for e in c["erros"]], ["170012", "11802"])
        self.assertEqual([(e["etapa"], e["status"]) for e in c["etapas"]],
                         [("Analysis & Synthesis", "ok"), ("Fitter", "falhou")])
        self.assertEqual(q.classificar_falha(c, 128.0)[0], "nao_cabe")

    def test_nao_roteia(self):
        c = q.parse_compile_log(ler(OPUS / "quartus_output_rv32i_a9" / "compilation" / "compile.log"))
        motivo, dica = q.classificar_falha(c, 27.0)
        self.assertEqual(motivo, "nao_roteia")
        self.assertIn("--roteamento-agressivo", dica)
        self.assertIn("188026", [a["id"] for a in c["avisos_criticos"]])

    def test_compila(self):
        c = q.parse_compile_log(ler(OPUS / "quartus_output_rv32im_a9r" / "compilation" / "compile.log"))
        self.assertTrue(c["compila"])
        self.assertIsNone(c["etapa_que_falhou"])
        self.assertEqual(c["erros"], [])
        self.assertEqual([e["etapa"] for e in c["etapas"]],
                         ["Analysis & Synthesis", "Fitter", "Assembler", "Timing Analyzer"])
        self.assertTrue(all(e["status"] == "ok" for e in c["etapas"]))
        self.assertEqual(q.classificar_falha(c, 19.0), (None, None))

    def test_log_cortado_no_meio_e_incompleta(self):
        texto = ler(OPUS / "quartus_output_rv32im_a9r" / "compilation" / "compile.log")
        cortado = texto[:texto.index("Info (170137)")]        # morreu durante o Fitter
        c = q.parse_compile_log(cortado)
        self.assertFalse(c["compila"])
        self.assertEqual(c["etapa_que_falhou"], "Fitter")
        self.assertEqual(q.classificar_falha(c, None)[0], "compilacao_incompleta")
        self.assertEqual(q.classificar_falha(q.parse_compile_log(""), None)[0], "compilacao_incompleta")


class TestRecursos(unittest.TestCase):

    def test_tabela_do_fitter(self):
        t = q.parse_tabela_recursos(ler(FIX / "fit_rpt_ok.txt"))
        self.assertEqual(t["Combinational ALUT usage for logic"]["uso"], "22,126")
        self.assertEqual(q._uso(t["Total LABs: partially or completely used"]),
                         {"usado": 4621, "total": 11356, "percentual": 41.0, "qualificador": None})
        self.assertEqual(q._uso(t["Secondary logic registers"])["qualificador"], "<")
        self.assertEqual(t["Peak interconnect usage (total/H/V)"]["uso"], "38.4% / 38.5% / 38.3%")
        self.assertEqual(q.parse_tabela_recursos("nada aqui"), {})

    def test_compilou(self):
        r = q.montar_recursos(ler(OPUS / "quartus_output_rv32im_a9r" / "reports" / "rv32im_a9r.fit.summary"),
                              ler(FIX / "fit_rpt_ok.txt"), None)
        self.assertEqual(r["fonte"], "fitter")
        self.assertTrue(r["cabe"])
        self.assertEqual((r["alms"]["usado"], r["alms"]["total"], r["alms"]["percentual"]), (21851, 113560, 19.0))
        self.assertEqual(r["luts"]["aluts_logica"], 22126)
        self.assertEqual(r["luts"]["por_numero_de_entradas"]["6"], 16226)
        self.assertEqual(r["registradores"], 33857)
        self.assertEqual(r["memoria"]["blocos_m10k"]["total"], 1220)
        self.assertEqual(r["dsp"]["usado"], 9)
        self.assertIn("M10K", r["nota_memoria"])              # 0 bits em bloco: virou flip-flop

    def test_nao_coube_ainda_mostra_quanto_passou(self):
        r = q.montar_recursos(ler(OPUS / "quartus_output_rv32i" / "reports" / "rv32i.fit.summary"),
                              ler(FIX / "fit_rpt_nao_cabe.txt"), None)
        self.assertFalse(r["cabe"])
        self.assertEqual(r["status_fit"], "Failed")
        self.assertEqual(r["alms"]["percentual"], 128.0)
        self.assertEqual(r["labs"]["percentual"], 131.0)

    def test_so_sintese_e_sintese_reprovada(self):
        r = q.montar_recursos(None, None, ler(OPUS / "quartus_output_rv32im_a9r" / "reports" / "rv32im_a9r.map.summary"))
        self.assertEqual((r["fonte"], r["registradores"], r["dsp"]["usado"]), ("sintese", 33857, 9))
        # sintese reprovada tambem escreve map.summary, so com "N/A"
        self.assertIsNone(q.montar_recursos(None, None, ler(FIX / "map_falhou.summary")))


class TestFrequenciaEPotencia(unittest.TestCase):

    def test_caminho_critico(self):
        cc = q.parse_caminho_critico(ler(OPUS / "quartus_output_rv32im_a9r" / "reports" / "critical_path.log"))
        self.assertEqual(cc["slack_ns"], -79.937)
        self.assertEqual(cc["situacao"], "VIOLATED")
        self.assertEqual(cc["de"], "program_counter:pc_inst|pc_reg[6]")
        self.assertEqual(cc["para"], "register_file:regfile_inst|regs[15][22]")
        self.assertEqual((cc["chegada_ns"], cc["requerido_ns"]), (104.274, 24.337))
        self.assertGreater(cc["celulas_no_caminho"], 100)
        self.assertIsNone(q.parse_caminho_critico("Report Timing: Found 0 setup paths"))

    def test_pior_tns(self):
        self.assertEqual(q.pior_tns_setup(ler(OPUS / "quartus_output_rv32im_a9r" / "reports" / "rv32im_a9r.sta.summary")),
                         -622000.311)

    def test_restricao_aplicada(self):
        self.assertEqual(q.avaliar_restricao(
            ler(OPUS / "quartus_output_rv32im_a9r" / "compilation" / "compile.log")), (True, True, []))

    def test_clock_que_nao_casa_com_porta_e_nao_confiavel(self):
        # capturado de verdade: cpu.toml com signal = "clk_errado"
        restrito, confiavel, motivos = q.avaliar_restricao(ler(FIX / "compile_clock_nao_casou.log"))
        self.assertFalse(restrito)
        self.assertFalse(confiavel)
        self.assertEqual(len(motivos), 2)                     # Fitter e TimeQuest repetem; fica um de cada
        self.assertTrue(any("332049" in m and "create_clock" in m for m in motivos))

    def test_potencia_e_estimativa(self):
        p = q.montar_potencia(ler(OPUS / "quartus_output_rv32im_a9r" / "reports" / "rv32im_a9r.pow.summary"))
        self.assertTrue(p["estimativa"])
        self.assertEqual((p["total_mw"], p["dinamica_nucleo_mw"], p["estatica_nucleo_mw"], p["io_mw"]),
                         (3722.23, 3117.44, 586.34, 18.44))
        self.assertIn("Low", p["confianca"])
        self.assertIsNone(q.montar_potencia(None))


class DockerFalso(q.Docker):
    """Faz o papel do container: grava, no projeto montado, os mesmos
    arquivos que o Quartus gravou nas execucoes reais."""

    def __init__(self, cenario: str):
        super().__init__("docker-falso")
        self.cenario = cenario
        self.chamadas: list[tuple[str | None, list[str]]] = []

    def conferir_servidor(self):
        return "falso"

    def escolher_imagem(self, candidatas):
        self.imagem = candidatas[0]
        return self.imagem

    def devolver_dono(self, pasta):
        pass

    def rodar(self, pasta, args, log, *, entrypoint=None, timeout_s=None):
        self.chamadas.append((entrypoint, list(args)))
        pasta = Path(pasta)
        if args == ["--version"]:
            log.write_text("Quartus Prime Shell\nVersion 25.1std.0 Build 1129 10/21/2025 SC Lite Edition\n")
        elif args[:2] == ["-t", "_qt_device.tcl"]:
            log.write_text("QT_DEVICE_COUNT=432\nQT_DEVICE_FOUND=1\n")
        elif args[0] == "analyze":
            rev = args[args.index("--revision") + 1]
            out = pasta / args[args.index("--output") + 1].removeprefix("/workspace/")
            of = pasta / "output_files"
            for d in (out / "compilation", out / "reports", out / "bitstream", of, pasta / "db"):
                d.mkdir(parents=True, exist_ok=True)
            if self.cenario == "erro":
                shutil.copy(FIX / "compile_erro_sintese.log", out / "compilation" / "compile.log")
                shutil.copy(FIX / "map_falhou.summary", of / f"{rev}.map.summary")
                return 1
            ev = OPUS / "quartus_output_rv32im_a9r"
            shutil.copy(ev / "compilation" / "compile.log", out / "compilation" / "compile.log")
            shutil.copy(ev / "compilation" / "fmax.log", out / "compilation" / "fmax.log")
            for suf in ("map.summary", "fit.summary", "sta.summary", "pow.summary"):
                shutil.copy(ev / "reports" / f"rv32im_a9r.{suf}", of / f"{rev}.{suf}")
            shutil.copy(FIX / "fit_rpt_ok.txt", of / f"{rev}.fit.rpt")
            (out / "bitstream" / f"{rev}.sof").write_bytes(b"sof")
            return 0
        elif entrypoint == "quartus_sta":
            shutil.copy(OPUS / "quartus_output_rv32im_a9r" / "reports" / "critical_path.log", log)
        elif entrypoint == "quartus_map":
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text("QT_RTL_CELLS=14\n")
        return 0


class TestExecucao(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.saida = Path(self._tmp.name) / "saida"

    def tearDown(self):
        self._tmp.cleanup()

    def executar(self, cenario, *extra, cpu="cpus/rv32i_monociclo"):
        args = q.parser_cli().parse_args([str(RAIZ / cpu), "--saida", str(self.saida), *extra])
        docker = DockerFalso(cenario)
        rc, rel = q.executar(args, docker=docker, avisar=lambda _msg: None)
        return rc, rel, docker

    def test_cpu_que_compila(self):
        rc, rel, docker = self.executar("ok", "--periodo-ns", "20")
        self.assertEqual((rc, rel["veredito"]), (0, "COMPILA"))
        # topo so com clk/rst -> preservacao ligada sozinha
        self.assertTrue(rel["sintese"]["preservar_logica"])
        self.assertIn('PRESERVE_FANOUT_FREE_NODE ON -to "|"', ler(self.saida / "comum.tcl"))
        [rev] = rel["revisoes"]
        f = rev["frequencia"]
        self.assertEqual((f["fmax_mhz"], f["alvo_mhz"], f["fmax_atende_alvo"]), (10.01, 50.0, False))
        self.assertEqual(f["slack_setup_pior_ns"], -83.204)
        self.assertFalse(f["fechamento_de_timing"])
        self.assertEqual(f["caminho_critico"]["de"], "program_counter:pc_inst|pc_reg[6]")
        self.assertEqual(rev["recursos"]["luts"]["aluts_logica"], 22126)
        self.assertEqual(rev["potencia"]["total_mw"], 3722.23)
        self.assertEqual(rev["netlist_rtl"]["celulas_topo"], 14)
        self.assertFalse(rev["logica_removida"])
        status = {k["id"]: k["status"] for k in rev["checagens"]}
        self.assertEqual(set(status.values()), {"ok"}, status)
        self.assertEqual(set(status), {"compilacao", "fit", "logica", "restricao", "slack", "fmax",
                                       "caminho_critico", "potencia", "netlist", "bitstream"})
        self.assertEqual([c["status"] for c in rel["checagens_do_ambiente"]], ["ok", "ok"])
        # relatorios escritos, db/ (centenas de MB) apagado, evidencia mantida
        self.assertEqual(json.loads(ler(self.saida / "relatorio.json"))["veredito"], "COMPILA")
        md = ler(self.saida / "relatorio.md")
        for trecho in ("### 1. Compila?", "### 2. Frequência", "### 3. Recursos", "### 4. Potência", "10,01 MHz"):
            self.assertIn(trecho, md)
        # `|` de nome de no do Quartus escapado: sem isso a tabela quebra
        self.assertIn("program_counter:pc_inst\\|pc_reg[6]", md)
        self.assertFalse((self.saida / "db").exists())
        self.assertTrue((self.saida / "quartus_output_padrao" / "reports" / "padrao.fit.summary").exists())
        self.assertIn("veredito: COMPILA", q.resumo_terminal(rel))

    def test_cpu_que_nao_compila(self):
        rc, rel, docker = self.executar("erro")
        self.assertEqual((rc, rel["veredito"]), (1, "NAO_COMPILA"))
        [rev] = rel["revisoes"]
        c = rev["compilacao"]
        self.assertEqual((c["motivo"], c["etapa_que_falhou"]), ("erro_de_sintese", "Analysis & Synthesis"))
        self.assertEqual(c["erros"][0]["arquivo"], "cpus/rv32i_monociclo/src/mono_alu.vhd")
        self.assertIsNone(rev["frequencia"])
        self.assertIsNone(rev["recursos"])
        self.assertIsNone(rev["potencia"])
        status = {k["id"]: k["status"] for k in rev["checagens"]}
        self.assertEqual(status["compilacao"], "falhou")
        self.assertEqual({s for i, s in status.items() if i != "compilacao"}, {"pulado"})
        # sem sintese nao ha netlist nem timing: nenhum quartus_sta/quartus_map rodou
        self.assertNotIn("quartus_sta", [e for e, _ in docker.chamadas])
        self.assertNotIn("quartus_map", [e for e, _ in docker.chamadas])
        self.assertIn("mono_alu.vhd:47", ler(self.saida / "relatorio.md"))

    def test_ambas_compila_duas_revisoes_na_ordem(self):
        rc, rel, docker = self.executar("ok", "--isa", "ambas")
        self.assertEqual([r["revisao"] for r in rel["revisoes"]], ["rv32i", "rv32im"])
        analyzes = [a[a.index("--revision") + 1] for e, a in docker.chamadas if a and a[0] == "analyze"]
        self.assertEqual(analyzes, ["rv32i", "rv32im"])

    def test_topo_com_saida_nao_preserva(self):
        _, rel, _ = self.executar("ok", cpu="implemetation_tests/opus_5_RISCVIM")
        self.assertFalse(rel["sintese"]["preservar_logica"])
        self.assertNotIn("PRESERVE_FANOUT_FREE_NODE", ler(self.saida / "comum.tcl"))

    def test_nao_apaga_pasta_que_nao_e_dela(self):
        self.saida.mkdir()
        (self.saida / "importante.txt").write_text("nao apague")
        with self.assertRaisesRegex(q.ErroDeEntrada, "nao foi criada por esta ferramenta"):
            self.executar("ok")
        self.assertTrue((self.saida / "importante.txt").exists())

    def test_rodar_de_novo_limpa_a_execucao_anterior(self):
        self.executar("ok")
        (self.saida / "sobra.txt").write_text("da execucao anterior")
        self.executar("erro")
        self.assertFalse((self.saida / "sobra.txt").exists())
        self.assertFalse((self.saida / "quartus_output_padrao" / "bitstream" / "padrao.sof").exists())


class TestDockerReal(unittest.TestCase):
    """So o que da para conferir sem subir container."""

    def test_sem_docker_no_path_e_erro_de_ambiente(self):
        with self.assertRaisesRegex(q.ErroDeAmbiente, "nao encontrado"):
            q.Docker("comando-que-nao-existe-quartus-testing").conferir_servidor()


if __name__ == "__main__":
    unittest.main()
