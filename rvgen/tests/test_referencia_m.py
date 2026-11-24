"""O modelo de referência do M bate com valores do riscv-tests e do riscv-rv32m.md."""

import unittest

from rvgen.referencia_m import M32, MIN, referencia

MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU = range(8)


def u(x):
    return x & M32


class TestReferenciaM(unittest.TestCase):

    def test_exemplos_da_spec(self):
        casos = [(MUL, 7, u(-3), u(-21)), (MULH, MIN, MIN, 0x40000000),
                 (MULHSU, M32, M32, M32), (MULHU, M32, M32, 0xFFFFFFFE),
                 (DIV, u(-7), 2, u(-3)), (DIVU, u(-7), 2, 0x7FFFFFFC),
                 (REM, u(-7), 2, M32), (REMU, u(-7), 2, 1),
                 (DIV, 5, 0, M32), (REM, 5, 0, 5), (DIV, MIN, M32, MIN), (REM, MIN, M32, 0)]
        for f3, a, b, esperado in casos:
            self.assertEqual(referencia(f3, a, b), esperado, (f3, hex(a), hex(b)))

    def test_valores_do_riscv_tests(self):
        # isa/rv32um/div.S, rem.S, divu.S, remu.S
        casos = [(DIV, 20, 6, 3), (DIV, u(-20), 6, u(-3)), (DIV, 20, u(-6), u(-3)),
                 (DIV, u(-20), u(-6), 3), (DIV, MIN, 1, MIN), (DIV, 1, 0, M32),
                 (DIVU, u(-20), 6, 715827879), (REM, u(-20), 6, u(-2)),
                 (REM, 20, u(-6), 2), (REMU, u(-20), 6, 2), (REMU, 1, 0, 1)]
        for f3, a, b, esperado in casos:
            self.assertEqual(referencia(f3, a, b), esperado, (f3, hex(a), hex(b)))


if __name__ == "__main__":
    unittest.main()


class TestProgramaDoOraculo(unittest.TestCase):

    def test_carregar_qualquer_valor_com_lui_e_addi(self):
        from rvgen.referencia_m import _carregar

        def executar(linhas):
            regs = {}
            for linha in linhas:
                op, resto = linha.split(None, 1)
                a = [x.strip() for x in resto.split(",")]
                regs[a[0]] = ((int(a[1], 16) << 12) if op == "lui"
                              else regs[a[1]] + int(a[2])) & M32
            return regs

        for v in (0, 1, 0x7FF, 0x800, 0xFFF, 0x1000, MIN, 0x7FFFFFFF, M32, 0x12345678, 0xFFFFF800):
            self.assertEqual(executar(_carregar("x5", v))["x5"], v, hex(v))

    def test_programa_cobre_os_256_pares_e_as_8_operacoes(self):
        from rvgen.referencia_m import BASE, OPERACOES, VALORES, programa
        fonte, esperados = programa()
        self.assertEqual(len(esperados), len(VALORES) ** 2 * 8)
        self.assertEqual({f3 for _, f3, _, _ in esperados}, set(range(8)))
        enderecos = [e for e, _, _, _ in esperados]
        self.assertEqual(len(set(enderecos)), len(enderecos))
        self.assertEqual(min(enderecos), BASE)
        for op in OPERACOES:
            self.assertIn(f"{op} x7, x5, x6", fonte)
        self.assertTrue(fonte.rstrip().endswith("halt: jal x0, halt"))
        # sem pseudoinstrucoes: o montador do rvgen as recusa
        self.assertNotIn("li ", fonte)
