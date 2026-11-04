#!/usr/bin/env python3
"""O caminho virtual do rvverify (barramento de 9 portas de specs/cpu.md), com GHDL de verdade.

Antes deste arquivo nenhum teste rodava o `tb_virtual`: `cpus/rv32i_gabarito`
é a primeira CPU que o exercita. Ele fixa três defeitos que só apareceram
rodando de verdade:

* o `tb_virtual` lia `data_addr` antes de a instrução assentar, então os
  stores iam para o endereço da instrução anterior e a RAM terminava zerada,
  mesmo numa CPU correta;
* o relatório de falha tinha `erro` como texto e `falhas` num formato próprio,
  e o `feedback` caía com `AttributeError` em vez de diagnosticar;
* uma CPU que nunca chega ao auto-laço precisa virar `travamento`.

Pulado quando não há GHDL ou cocotb 2.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

pytest.importorskip("cocotb_tools", reason="cocotb 2 nao esta instalado")

from rvverify.conformance import run_conformance  # noqa: E402

pytestmark = pytest.mark.skipif(shutil.which("ghdl") is None,
                                reason="GHDL nao esta no PATH; o caminho virtual exige simulador real")

GABARITO = Path(__file__).resolve().parent.parent.parent / "cpus" / "rv32i_gabarito"


def _copia_alterada(tmp_path: Path, antigo: str, novo: str) -> Path:
    cpu = tmp_path / "cpu_alterada"
    shutil.copytree(GABARITO, cpu)
    fonte = cpu / "src" / "cpu.vhd"
    texto = fonte.read_text(encoding="utf-8")
    assert antigo in texto, "o trecho a alterar sumiu do gabarito"
    fonte.write_text(texto.replace(antigo, novo), encoding="utf-8")
    return cpu / "cpu.toml"


def test_gabarito_passa_a_baseline_rv32i_inteira(tmp_path):
    rel = run_conformance(GABARITO / "cpu.toml", tmp_path, stages=("rv32i",))
    assert rel["compilacao"]["ok"] is True
    assert [c["name"] for c in rel["casos"] if not c["passed"]] == []
    assert len(rel["casos"]) == 24
    # inclui loads e stores de byte, meia palavra e palavra
    assert any(c["name"] == "load_store_larguras" and c["passed"] for c in rel["casos"])


def test_cpu_com_defeito_e_reprovada_com_diagnostico_de_valor(tmp_path):
    manifesto = _copia_alterada(tmp_path, "unsigned(rs1_val) - unsigned(alu_b)",
                                "unsigned(rs1_val) + unsigned(alu_b)")      # SUB vira ADD
    rel = run_conformance(manifesto, tmp_path / "w", stages=("rv32i",), only={"rv32i/sub"})
    [caso] = rel["casos"]
    assert caso["passed"] is False
    assert caso["diagnostico"]["tipo"] == "valor"
    assert caso["diagnostico"]["total_divergencias"] > 0
    assert caso["diagnostico"]["divergencias"][0]["endereco"].startswith("0x00fc81")


def test_cpu_que_nunca_para_vira_travamento(tmp_path):
    # JAL deixa de saltar: o auto-laço `jal x0, 0` nunca prende o PC
    manifesto = _copia_alterada(tmp_path, "jal_target                                                        when opcode = OP_JAL    else",
                                "pc_plus4                                                          when opcode = OP_JAL    else")
    rel = run_conformance(manifesto, tmp_path / "w", stages=("rv32i",), only={"rv32i/x0_imutavel"})
    [caso] = rel["casos"]
    assert caso["passed"] is False
    assert caso["diagnostico"]["tipo"] == "travamento"
    assert caso["diagnostico"]["dados"]["max_ciclos"] > 0
