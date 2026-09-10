#!/usr/bin/env python3
"""Testes do leitor de `cpu.toml`. pytest puro -- sem GHDL, sem cocotb.

REQ: FR-RV-21, FR-RV-24, NFR-RV-02.

Estes testes cobrem o contrato do manifesto, que e a unica coisa que um aluno
escreve a mao para submeter uma CPU ao validador: manifesto valido, campo
obrigatorio ausente, modo de parada que exige sinal nao declarado e caminho de
observacao malformado. A regra que eles protegem e sempre a mesma -- o
validador recusa com uma mensagem util em vez de assumir um default silencioso
que daria resultado errado na simulacao.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rvverify.manifest import (  # noqa: E402
    CpuManifest,
    ManifestError,
    load_manifest,
)

RISCV32I_MANIFEST = REPO_ROOT / "examples" / "RISCV32I" / "cpu.toml"


# --------------------------------------------------------------------------
# fixtures: um manifesto minimo valido, em forma de dicionario
# --------------------------------------------------------------------------

def minimal() -> dict:
    """O menor manifesto que o validador aceita."""
    return {
        "design": {
            "name": "cpu_minima",
            "top": "CPU",
            "std": "08",
            "sources": ["src/cpu.vhd"],
        },
        "clock": {"signal": "clk", "period_ns": 10},
        "reset": {"signal": "rst", "active": "high", "cycles": 3},
        "memory": {"ram_base": 0x1000, "ram_bytes": 512},
        "observe": {"ram": "data_memory.data_ram.memory"},
        "halt": {"mode": "fixed_cycles", "cycles": 200},
    }


def build(raw: dict) -> CpuManifest:
    return CpuManifest.from_dict(raw, Path("cpu.toml"))


def write(tmp_path: Path, text: str) -> Path:
    p = tmp_path / "cpu.toml"
    p.write_text(text, encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# manifesto valido
# --------------------------------------------------------------------------

class TestManifestoValido:
    def test_minimo_carrega(self):
        m = build(minimal())
        assert m.design.top == "CPU"
        assert m.clock.period_ns == 10
        assert m.memory.ram_words == 128
        assert m.halt.mode == "fixed_cycles"

    def test_cpu_real_do_repositorio(self):
        """O `cpu.toml` da CPU pipeline tem de ser valido e completo."""
        m = load_manifest(RISCV32I_MANIFEST)

        assert m.design.top == "CPU"
        assert len(m.design.sources) == 20
        assert m.design.sources[0] == "src/cpu_package.vhd"   # ordem de analise
        assert m.design.sources[-1] == "src/CPU.vhd"

        assert m.clock.signal == "clk" and m.clock.period_ns == 10
        assert m.reset.signal == "rst" and m.reset.active == "high"
        assert m.memory.ram_base == 0x00FC8100
        assert m.memory.ram_bytes == 512

        assert m.observe.ram == "data_memory.data_ram.memory"
        assert m.observe.registers == "register_file.registers"

        # pipeline especulativo -> commit_pc, nunca fetch_pc (ADR-008)
        assert m.halt.mode == "commit_pc"
        assert m.halt.pc == "pc_e" and m.halt.taken == "jump_e"

        assert m.metrics.can_derive_instructions
        assert m.metrics.m_dispatch == "m_dispatch_e"

    def test_fontes_do_cpu_real_existem_na_ordem_declarada(self):
        m = load_manifest(RISCV32I_MANIFEST)
        paths = m.source_paths()
        assert len(paths) == 20
        assert all(p.exists() for p in paths)
        assert paths[-1].name == "CPU.vhd"

    def test_polaridade_do_reset(self):
        alto = build(minimal())
        assert (alto.reset.asserted, alto.reset.released) == (1, 0)

        raw = minimal()
        raw["reset"]["active"] = "low"
        baixo = build(raw)
        assert (baixo.reset.asserted, baixo.reset.released) == (0, 1)

    def test_endereco_vira_indice_de_palavra(self):
        m = build(minimal())
        assert m.memory.contains(0x1000)
        assert m.memory.word_index(0x1000) == 0
        assert m.memory.word_index(0x1008) == 2
        assert not m.memory.contains(0x1000 + 512)

    def test_generic_da_chamada_vence_o_manifesto(self):
        """A suite alterna RV32M caso a caso; o manifesto e so o default."""
        raw = minimal()
        raw["design"]["generics"] = {"RV32M_ENABLE": True, "ROM_SIZE_WORDS": 1024}
        m = build(raw)
        assert m.generics_for()["RV32M_ENABLE"] is True
        merged = m.generics_for({"RV32M_ENABLE": "false"})
        assert merged["RV32M_ENABLE"] == "false"
        assert merged["ROM_SIZE_WORDS"] == 1024

    def test_toml_de_verdade_com_hexadecimal(self, tmp_path):
        p = write(tmp_path, """
[design]
name = "x"
top  = "CPU"
sources = ["a.vhd"]

[clock]
signal = "clk"
period_ns = 20

[reset]
signal = "reset_n"
active = "low"

[memory]
ram_base  = 0x00FC8100
ram_bytes = 256

[observe]
ram = "mem.words"

[halt]
mode = "fetch_pc"
pc   = "pc"
""")
        m = load_manifest(p)
        assert m.memory.ram_base == 0x00FC8100
        assert m.reset.asserted == 0            # ativo em nivel baixo
        assert m.reset.cycles == 3              # default documentado
        assert m.halt.drain == 5                # default documentado

    def test_load_aceita_o_diretorio(self, tmp_path):
        write(tmp_path, RISCV32I_MANIFEST.read_text(encoding="utf-8"))
        assert load_manifest(tmp_path).design.name == "rv32i_pipeline"


# --------------------------------------------------------------------------
# campo obrigatorio faltando
# --------------------------------------------------------------------------

class TestCampoObrigatorioFaltando:
    @pytest.mark.parametrize("tabela", ["design", "clock", "reset", "memory",
                                        "observe", "halt"])
    def test_tabela_obrigatoria_ausente(self, tabela):
        raw = minimal()
        del raw[tabela]
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert f"[{tabela}]" in str(e.value)
        assert "obrigatoria" in str(e.value)

    @pytest.mark.parametrize("tabela,campo", [
        ("design", "name"),
        ("design", "top"),
        ("design", "sources"),
        ("clock", "signal"),
        ("clock", "period_ns"),
        ("reset", "signal"),
        ("memory", "ram_base"),
        ("memory", "ram_bytes"),
        ("observe", "ram"),
        ("halt", "mode"),
    ])
    def test_campo_obrigatorio_ausente(self, tabela, campo):
        raw = minimal()
        del raw[tabela][campo]
        with pytest.raises(ManifestError) as e:
            build(raw)
        msg = str(e.value)
        assert f"`{campo}`" in msg and f"[{tabela}]" in msg

    def test_observe_ram_e_obrigatorio_mesmo_com_o_resto_presente(self):
        """Sem RAM observavel nao ha o que verificar -- nem no modo mais fraco."""
        raw = minimal()
        raw["observe"] = {"registers": "rf.regs", "pc_fetch": "pc"}
        with pytest.raises(ManifestError, match=r"`ram`"):
            build(raw)

    def test_sources_vazio(self):
        raw = minimal()
        raw["design"]["sources"] = []
        with pytest.raises(ManifestError, match="ORDEM DE ANALISE"):
            build(raw)

    def test_rom_init_file_sem_generic(self):
        """Carregar programa por arquivo exige dizer QUAL generic o recebe."""
        raw = minimal()
        raw["program"] = {"mode": "rom_init_file"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "[program].generic" in str(e.value)

    def test_arquivo_de_manifesto_inexistente(self, tmp_path):
        with pytest.raises(ManifestError, match="nao encontrado"):
            load_manifest(tmp_path / "nao_existe.toml")

    def test_toml_invalido(self, tmp_path):
        p = write(tmp_path, "[design\nname = 'x'\n")
        with pytest.raises(ManifestError, match="TOML invalido"):
            load_manifest(p)

    def test_fonte_declarada_que_nao_existe(self, tmp_path):
        p = write(tmp_path, RISCV32I_MANIFEST.read_text(encoding="utf-8"))
        m = load_manifest(p)          # o diretorio temporario nao tem src/
        with pytest.raises(ManifestError) as e:
            m.source_paths()
        assert "src/CPU.vhd" in str(e.value)

    def test_valores_de_tipo_errado(self):
        raw = minimal()
        raw["clock"]["period_ns"] = "dez"
        with pytest.raises(ManifestError, match="inteiro"):
            build(raw)

    def test_ram_bytes_nao_multiplo_de_quatro(self):
        raw = minimal()
        raw["memory"]["ram_bytes"] = 510
        with pytest.raises(ManifestError, match="multiplo de 4"):
            build(raw)

    def test_valor_fora_do_conjunto_aceito(self):
        raw = minimal()
        raw["reset"]["active"] = "alto"
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "high" in str(e.value) and "low" in str(e.value)


# --------------------------------------------------------------------------
# modo de parada que exige sinal nao declarado
# --------------------------------------------------------------------------

class TestModoDeParada:
    def test_commit_pc_sem_pc_nem_taken(self):
        raw = minimal()
        raw["halt"] = {"mode": "commit_pc"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        msg = str(e.value)
        assert "commit_pc" in msg and "`pc`" in msg and "`taken`" in msg

    def test_commit_pc_sem_taken(self):
        """Sem o sinal de salto tomado, uma bolha especulativa passaria por fim."""
        raw = minimal()
        raw["halt"] = {"mode": "commit_pc", "pc": "pc_e"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "`taken`" in str(e.value)
        assert "especulativa" in str(e.value)

    def test_fetch_pc_sem_pc(self):
        raw = minimal()
        raw["halt"] = {"mode": "fetch_pc"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        msg = str(e.value)
        assert "fetch_pc" in msg and "`pc`" in msg
        assert "especulativa" in msg          # o aviso do ADR-008 esta na msg

    def test_fixed_cycles_sem_cycles(self):
        raw = minimal()
        raw["halt"] = {"mode": "fixed_cycles"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "`cycles`" in str(e.value)

    def test_modo_desconhecido(self):
        raw = minimal()
        raw["halt"] = {"mode": "quando_der"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        msg = str(e.value)
        assert all(k in msg for k in ("commit_pc", "fetch_pc", "fixed_cycles"))

    def test_modos_completos_sao_aceitos(self):
        raw = minimal()
        raw["halt"] = {"mode": "commit_pc", "pc": "pc_e", "taken": "jump_e",
                       "drain": 5}
        assert build(raw).halt.measures_cycles

        raw["halt"] = {"mode": "fetch_pc", "pc": "pc_f"}
        assert build(raw).halt.measures_cycles

        raw["halt"] = {"mode": "fixed_cycles", "cycles": 60}
        # fixed_cycles nao observa o fim do programa: nao mede ciclos
        assert not build(raw).halt.measures_cycles


# --------------------------------------------------------------------------
# caminho de observacao malformado
# --------------------------------------------------------------------------

class TestCaminhoDeObservacao:
    @pytest.mark.parametrize("ruim", [
        "data_memory..memory",       # segmento vazio
        ".data_memory.memory",       # ponto inicial
        "data_memory.memory.",       # ponto final
        "data memory.memory",        # espaco
        "memory[0]",                 # indice
        "9memory",                   # comeca com digito
        "dut/mem/memory",            # separador errado
        "",                          # vazio
        "   ",                       # so espaco
    ])
    def test_ram_malformada(self, ruim):
        raw = minimal()
        raw["observe"]["ram"] = ruim
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "[observe].ram" in str(e.value)

    @pytest.mark.parametrize("secao,campo", [
        ("observe", "registers"),
        ("observe", "pc_fetch"),
        ("metrics", "stall"),
        ("metrics", "m_dispatch"),
    ])
    def test_caminho_opcional_malformado_tambem_e_recusado(self, secao, campo):
        raw = minimal()
        raw.setdefault(secao, {})[campo] = "a..b"
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert f"[{secao}].{campo}" in str(e.value)

    def test_mensagem_explica_o_formato_esperado(self):
        raw = minimal()
        raw["observe"]["ram"] = "data_memory..memory"
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "separados por ponto" in str(e.value)

    def test_caminho_aninhado_valido(self):
        raw = minimal()
        raw["observe"]["ram"] = "a.b.c.d_1"
        assert build(raw).observe.ram == "a.b.c.d_1"

    def test_halt_tambem_valida_caminho(self):
        raw = minimal()
        raw["halt"] = {"mode": "commit_pc", "pc": "pc_e[0]", "taken": "jump_e"}
        with pytest.raises(ManifestError) as e:
            build(raw)
        assert "[halt].pc" in str(e.value)


# --------------------------------------------------------------------------
# degradacao graciosa (NFR-RV-02)
# --------------------------------------------------------------------------

class TestDegradacaoGraciosa:
    def test_so_ram_reporta_o_que_falta(self):
        """Sem registradores e sem [metrics], o manifesto diz o que nao ve."""
        caps = build(minimal()).observability()
        assert caps["ram"] is True
        assert caps["registers"] is False
        assert caps["instructions"] is False
        assert caps["m_instructions"] is False
        assert caps["cycles"] is False        # fixed_cycles nao mede ciclos
        texto = " ".join(caps["unobserved"])
        assert "registers" in texto and "instrucoes" in texto

    def test_registradores_declarados(self):
        raw = minimal()
        raw["observe"]["registers"] = "register_file.registers"
        caps = build(raw).observability()
        assert caps["registers"] is True
        assert not any("registers" in u for u in caps["unobserved"])

    def test_metricas_parciais_nao_derivam_instrucoes(self):
        """Faltando UM dos tres sinais, instrucoes viram null -- nao um chute."""
        raw = minimal()
        raw["metrics"] = {"stall": "stall_pc", "flush_d": "flush_d"}
        m = build(raw)
        assert m.metrics.declared
        assert not m.metrics.can_derive_instructions
        assert m.metrics.missing_for_instructions() == ["flush_f"]
        assert any("flush_f" in u for u in m.observability()["unobserved"])

    def test_metricas_completas_liberam_instrucoes(self):
        raw = minimal()
        raw["observe"]["registers"] = "register_file.registers"
        raw["halt"] = {"mode": "commit_pc", "pc": "pc_e", "taken": "jump_e"}
        raw["metrics"] = {"stall": "s", "flush_d": "fd", "flush_f": "ff",
                          "m_dispatch": "md"}
        caps = build(raw).observability()
        assert caps["instructions"] and caps["m_instructions"] and caps["cycles"]
        assert caps["unobserved"] == []

    def test_cpu_real_observa_tudo(self):
        caps = load_manifest(RISCV32I_MANIFEST).observability()
        assert caps["unobserved"] == []
        assert all(caps[k] for k in ("ram", "registers", "cycles",
                                     "instructions", "m_instructions"))
