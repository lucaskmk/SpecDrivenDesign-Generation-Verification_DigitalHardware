#!/usr/bin/env python3
"""Contrato do montador determinístico usado pelos testes Cocotb RV32I."""

from __future__ import annotations

import unittest

from rvgen.riscv_asm import (ErroAssemblyRV32I, assemble_rv32i, assemble_rv32im,
                             validar_assembly_rv32i, validar_assembly_rv32im)


class TestAssemblyRV32I(unittest.TestCase):
    def test_monta_instrucoes_e_resolve_label(self):
        programa = assemble_rv32i("""
            lui x1, 1
            addi x1, x1, -1
            sw x1, 0(x1)
        halt:
            jal x0, halt
        """)
        self.assertEqual(programa, {
            0x00: 0x000010B7,
            0x04: 0xFFF08093,
            0x08: 0x0010A023,
            0x0C: 0x0000006F,
        })

    def test_recusa_pseudoinstrucao_e_diretiva(self):
        with self.assertRaisesRegex(ErroAssemblyRV32I, "instrução RV32I permitida"):
            validar_assembly_rv32i("li x1, 1")
        with self.assertRaisesRegex(ErroAssemblyRV32I, "diretivas"):
            validar_assembly_rv32i(".include \"estranho.s\"")

    def test_recusa_extensao_fora_do_rv32i(self):
        with self.assertRaisesRegex(ErroAssemblyRV32I, "instrução RV32I permitida"):
            validar_assembly_rv32i("mul x1, x2, x3")

    def test_jumps_exigem_labels_para_nao_ambiguidade_endereco_deslocamento(self):
        with self.assertRaisesRegex(ErroAssemblyRV32I, "use um label"):
            validar_assembly_rv32i("jal x1, 8", exigir_labels_controle=True)
        validar_assembly_rv32i("jal x1, -8")
        validar_assembly_rv32i("jal x1, alvo\nalvo: jal x0, alvo",
                               exigir_labels_controle=True)

    def test_rv32im_adiciona_mas_nao_altera_perfil_rv32i(self):
        with self.assertRaisesRegex(ErroAssemblyRV32I, "RV32I permitida"):
            validar_assembly_rv32i("mul x1, x2, x3")
        validar_assembly_rv32im("mul x1, x2, x3")
        self.assertEqual(assemble_rv32im("mul x1, x2, x3")[0] & 0x7F, 0x33)


if __name__ == "__main__":
    unittest.main()
