#!/usr/bin/env python3
"""Diagnóstico de falha, sem simulador: as regras de `rvverify.feedback`.

REQ: FR-RV-28 (diagnóstico estruturado), FR-RV-23 (o esperado e a detecção de
instrução trocada vêm do modelo de referência), NFR-RV-02.

A parte que depende do GHDL — um defeito real produzindo o diagnóstico — está
em `test_diagnostico.py`. Aqui ficam as regras, exercitadas com relatórios
montados à mão no mesmo formato que `tb_generic.py` grava.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from rvverify import feedback  # noqa: E402
from rvverify._ferramentas import ref  # noqa: E402
from rvverify.conformance import (  # noqa: E402
    _pairs,
    build_cases,
    catalog,
)

BASE = 0x00FC8100
PARES = _pairs()


def _obtidos(op: str) -> list[int]:
    f = ref.apply_m if op in feedback.M_OPS else ref.apply_i
    return [f(op, a, b) for a, b in PARES]


# ---------------------------------------------------------------------------
# instrução trocada
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("esperada, executada", [
    ("sra", "srl"),     # funct7 ignorado no deslocamento
    ("sub", "add"),     # funct7 ignorado na soma
    ("mul", "add"),     # extensão M decodificada como base (mesmo funct3)
    ("div", "xor"),
    ("remu", "and"),
    ("mulhsu", "mulh"),  # rs2 tratado como com sinal
])
def test_reconhece_instrucao_executada_no_lugar(esperada, executada):
    assert feedback.detectar_confusao(esperada, PARES, _obtidos(executada)) == executada


def test_resultado_sempre_zero_vira_zero():
    assert feedback.detectar_confusao("mul", PARES, [0] * len(PARES)) == "zero"


def test_resultado_igual_ao_primeiro_operando():
    obtidos = [a for a, _ in PARES]
    assert feedback.detectar_confusao("xor", PARES, obtidos) == "rs1"


def test_um_unico_valor_diferente_descarta_o_candidato():
    obtidos = _obtidos("srl")
    obtidos[5] ^= 0x1
    assert feedback.detectar_confusao("sra", PARES, obtidos) is None


def test_lixo_nao_sugere_nada():
    obtidos = [(0x9E3779B9 * (i + 1)) & 0xFFFFFFFF for i in range(len(PARES))]
    assert feedback.detectar_confusao("add", PARES, obtidos) is None


def test_dica_de_m_decodificada_como_base_fala_do_funct7():
    texto = feedback.dica_confusao("mul", "add", 64)
    assert "funct7" in texto and "0000001" in texto


def test_dica_de_sra_como_srl_fala_do_bit_30():
    texto = feedback.dica_confusao("sra", "srl", 64)
    assert "bit 30" in texto


# ---------------------------------------------------------------------------
# diagnosticar()
# ---------------------------------------------------------------------------

def _relatorio_sra_como_srl() -> tuple[dict, dict]:
    caso = next(c for c in build_cases(BASE) if c.name == "sra")
    obtidos = _obtidos("srl")
    enderecos = sorted(caso.expect_ram)
    falhas = [{"tipo": "ram", "endereco": a, "esperado": caso.expect_ram[a],
               "obtido": g}
              for a, g in zip(enderecos, obtidos) if caso.expect_ram[a] != g]
    rel = {
        "resultado": "falhou",
        "falhas": falhas,
        "erro": None,
        "cycles": 321,
        "ram_dump": {hex(a): g for a, g in zip(enderecos, obtidos)},
    }
    kw = {"rotulos": caso.labels, "pares": caso.pairs, "enderecos_pares": enderecos}
    return rel, kw


def test_valor_divergente_traz_endereco_entrada_esperado_e_obtido():
    rel, kw = _relatorio_sra_como_srl()
    diag = feedback.diagnosticar(nome="sra", relatorio=rel, **kw)

    assert diag["tipo"] == "valor"
    assert diag["confusao"] == "srl"
    assert diag["total_divergencias"] == len(rel["falhas"]) > 0
    d = diag["divergencias"][0]
    assert d["onde"].startswith("RAM[0x00fc81")
    assert d["entrada"].startswith("sra(0x")
    assert d["esperado"].startswith("0x") and d["obtido"].startswith("0x")
    assert isinstance(d["esperado_dec"], int)
    assert "SRL" in diag["resumo"]
    assert "bit 30" in diag["dica"]


def test_divergencias_sao_limitadas_mas_o_total_nao():
    rel, kw = _relatorio_sra_como_srl()
    diag = feedback.diagnosticar(nome="sra", relatorio=rel, limite=2, **kw)
    assert len(diag["divergencias"]) == 2
    assert diag["total_divergencias"] == len(rel["falhas"])


def test_travamento_usa_os_dados_estruturados():
    rel = {"resultado": "falhou", "falhas": [], "erro": {
        "tipo": "travamento", "mensagem": "CPU nao terminou em 500 ciclos",
        "dados": {"max_ciclos": 500, "pcs_mais_visitados": [[0x40, 480]],
                  "enderecos_de_parada": [0x1C], "pc_observavel": True},
    }}
    diag = feedback.diagnosticar(nome="x0_imutavel", relatorio=rel)
    assert diag["tipo"] == "travamento"
    assert "500 ciclos" in diag["resumo"]
    assert "0x00000040" in diag["dica"]          # onde a CPU ficou presa


def test_compilacao_aponta_arquivo_e_linha():
    erros = [{"arquivo": "alu.vhd", "caminho": "src/alu.vhd", "linha": 42,
              "coluna": 7, "tempo": None, "mensagem": "no declaration for \"x\""}]
    diag = feedback.diagnosticar(nome="add", relatorio=None,
                                 erros_compilacao=erros, mensagem_forcada="falhou")
    assert diag["tipo"] == "compilacao"
    assert diag["resumo"].startswith("alu.vhd:42:")
    assert diag["erros_ghdl"] == erros


def test_simulacao_abortada_sem_relatorio_vem_do_log():
    log = ("../../src/ieee2008/numeric_std-body.vhdl:3036:7:@0ms:(assertion "
           "warning): NUMERIC_STD.TO_INTEGER: metavalue detected\n"
           "ghdl:error: index (1069604864) out of bounds (0 to 127) at "
           "data_ram.vhd:48\n")
    diag = feedback.diagnosticar(nome="add", relatorio=None, log_texto=log,
                                 excecao=RuntimeError("abortou"))
    assert diag["tipo"] == "simulacao"
    assert "out of bounds" in diag["resumo"]
    assert "metavalue" not in diag["mensagem"]
    assert "restrição 3" in diag["dica"]


def test_observacao_repassa_a_mensagem_do_harness():
    rel = {"resultado": "falhou", "falhas": [], "erro": {
        "tipo": "observacao",
        "mensagem": "o manifesto declara [observe].ram = 'x.y' mas 'x' nao existe",
    }}
    diag = feedback.diagnosticar(nome="add", relatorio=rel)
    assert diag["tipo"] == "observacao"
    assert "nao existe" in diag["resumo"]
    assert "INSTÂNCIAS" in diag["dica"]


def test_resumo_em_texto_e_legivel():
    rel, kw = _relatorio_sra_como_srl()
    linhas = feedback.resumo_em_texto(
        feedback.diagnosticar(nome="sra", relatorio=rel, **kw))
    assert linhas[0].startswith("Valor errado na RAM:")
    assert any("esperado 0x" in l for l in linhas)
    assert linhas[-1].startswith("  sugestão:")


# ---------------------------------------------------------------------------
# catálogo
# ---------------------------------------------------------------------------

def test_catalogo_tem_os_35_casos_com_id_unico():
    cat = catalog()
    assert len(cat) == 35
    assert len({c["id"] for c in cat}) == 35
    assert sum(1 for c in cat if c["etapa"] == "rv32i") == 24
    assert sum(1 for c in cat if c["etapa"] == "rv32m") == 11
    assert all(c["descricao"] and c["requisitos"] for c in cat)


def test_caso_jal_agora_verifica_auipc_de_verdade():
    """O nome prometia AUIPC e o programa nao tinha AUIPC nenhum."""
    from rvverify.asm import assemble_with_symbols

    caso = next(c for c in build_cases(BASE) if c.name == "jal_jalr_lui_auipc")
    assert "auipc" in caso.asm
    _, simbolos = assemble_with_symbols(caso.asm, base_address=0, allow_m=False)
    assert caso.expect_ram[BASE + 8] == simbolos["aui"] + 0x12000


def test_todo_slot_esperado_tem_rotulo():
    for caso in build_cases(BASE):
        faltando = set(caso.expect_ram) - set(caso.labels)
        assert not faltando, f"{caso.name}: slots sem rotulo {sorted(faltando)}"
