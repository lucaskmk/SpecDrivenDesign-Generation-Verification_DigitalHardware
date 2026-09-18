"""Contrato mínimo da suíte de conformidade.

REQ: FR-RV-22, FR-RV-34, FR-RV-35.

Este teste não substitui GHDL. Ele impede que uma alteração futura reduza a
suíte silenciosamente: cada operação prevista pela cobertura precisa continuar
com um caso executável e requisitos associados.
"""

from __future__ import annotations

from rvverify.conformance import catalog


def test_cobertura_de_operacoes_rv32i_e_im() -> None:
    nomes = {item["nome"] for item in catalog()}
    assert {
        "add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu",
        "addi", "andi", "ori", "xori", "slti", "sltiu", "slli", "srli", "srai",
        "branches", "jal_jalr_lui_auipc", "load_store_larguras",
        "x0_imutavel", "laco_com_dependencia",
    } <= nomes
    assert {"mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu",
            "divisao_por_zero", "overflow_da_divisao", "misto_rv32i_rv32m"} <= nomes


def test_cada_caso_tem_requisito_e_descricao() -> None:
    for item in catalog():
        assert item["id"].count("/") == 1
        assert item["requisitos"]
        assert item["descricao"]
