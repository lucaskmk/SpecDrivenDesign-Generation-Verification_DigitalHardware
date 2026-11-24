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
