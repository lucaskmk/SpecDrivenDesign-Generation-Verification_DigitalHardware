from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rvgen.vcd import resumir


class TestResumoVCD(unittest.TestCase):
    def test_amostra_flancos_e_preserva_desconhecido(self):
        with tempfile.TemporaryDirectory() as tmp:
            vcd = Path(tmp) / "a.vcd"
            vcd.write_text("""$timescale 1 ns $end
$scope module cpu $end
$var reg 1 ! clk $end
$var reg 8 \" result[7:0] $end
$upscope $end
$enddefinitions $end
#0
0!
b00000000 \"
#5
1!
b10x00001 \"
#10
0!
#15
1!
b00001111 \"
""", encoding="utf-8")
            resumo = resumir(vcd, ["dut.clk", "dut.result", "dut.absent"], falha_ns=15)
        self.assertEqual(resumo["missing"], ["dut.absent"])
        self.assertEqual(len(resumo["samples"]), 2)
        self.assertEqual(resumo["samples"][0]["values"]["dut.result"], "0b10x00001")
        self.assertEqual(resumo["samples"][1]["values"]["dut.result"], "0x0F")
