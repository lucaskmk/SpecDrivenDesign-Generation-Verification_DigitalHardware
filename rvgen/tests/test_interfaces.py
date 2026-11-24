#!/usr/bin/env python3
"""Testes da checagem do combinado entre blocos (`rvgen interfaces`). Sem GHDL."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from rvgen import interfaces as itf
from rvgen.config import REPO_ROOT

CONTROLE = '''library ieee;
use ieee.std_logic_1164.all;
entity controle is
    port(
        instr : in std_logic_vector(31 downto 0);
        op    : out std_logic_vector(2 downto 0);  -- codigo para a alu
        sel   : out std_logic_vector(1 downto 0)
    );
end controle;
architecture rtl of controle is
begin
    process(all)
    begin
        op <= "000";
        sel <= "00";
        case instr(6 downto 0) is
            when "0110011" => op <= "001";
            when "0010011" => op <= "111";   -- a alu nao conhece 111
            when others => sel <= "11";       -- o topo nao conhece 11
        end case;
    end process;
end rtl;
'''

ALU = '''library ieee;
use ieee.std_logic_1164.all;
entity alu is
    port(
        op : in std_logic_vector(2 downto 0);
        y  : out std_logic_vector(31 downto 0)
    );
end alu;
architecture rtl of alu is
begin
    process(all)
    begin
        case op is
            when "000" | "001" => y <= (others => '0');
            when "010" =>
                case y(1 downto 0) is       -- case aninhado nao conta para `op`
                    when "11" => null;
                    when others => null;
                end case;
            when others => y <= (others => '1');
        end case;
    end process;
end rtl;
'''

TOPO = '''library ieee;
use ieee.std_logic_1164.all;
entity cpu is
    port(clk : in std_logic);
end cpu;
architecture rtl of cpu is
    signal instr : std_logic_vector(31 downto 0);
    signal op : std_logic_vector(2 downto 0);
    signal sel : std_logic_vector(1 downto 0);
    signal y : std_logic_vector(31 downto 0);
begin
    u_c : entity work.controle port map (instr => instr, op => op, sel => sel);
    u_a : entity work.alu port map (op => op, y => y);
    process(all)
    begin
        case sel is
            when "00" => null;
            when "01" => null;
            when others => null;
        end case;
    end process;
end rtl;
'''


class TestInterfaces(unittest.TestCase):

    def cpu(self, raiz: Path, alu: str = ALU) -> Path:
        (raiz / "src").mkdir()
        for nome, texto in (("controle", CONTROLE), ("alu", alu), ("cpu", TOPO)):
            (raiz / "src" / f"{nome}.vhd").write_text(texto, encoding="utf-8")
        return raiz

    def test_codigo_que_o_bloco_nao_decodifica_e_problema(self):
        with tempfile.TemporaryDirectory() as tmp:
            ligacoes = itf.checar_cpu(self.cpu(Path(tmp)))
        por_sinal = {l.sinal: l for l in ligacoes}
        op = por_sinal["op"]
        self.assertEqual(op.emitidos, {"000", "001", "111"})
        self.assertEqual(op.decodificados, {"000", "001", "010"})   # sem o "11" aninhado
        self.assertEqual(op.sem_decodificacao, {"111"})
        self.assertEqual(op.nunca_emitidos, {"010"})
        self.assertTrue(op.problema)
        # no topo, codigo sem decodificacao e so aviso
        sel = por_sinal["sel"]
        self.assertEqual(sel.sem_decodificacao, {"11"})
        self.assertFalse(sel.problema)
        self.assertEqual([l.sinal for l in itf.problemas(ligacoes)], ["op"])
        texto = itf.texto_relatorio(Path(tmp), ligacoes)
        self.assertIn("PROBLEMA op", texto)
        self.assertIn("aviso    sel", texto)

    def test_combinado_certo_nao_acusa(self):
        with tempfile.TemporaryDirectory() as tmp:
            alu = ALU.replace('when "010" =>', 'when "010" | "111" =>')
            ligacoes = itf.checar_cpu(self.cpu(Path(tmp), alu))
        self.assertEqual(itf.problemas(ligacoes), [])

    def test_comentario_nao_conta(self):
        self.assertEqual(itf.emitidos('architecture a of b is begin -- op <= "101";\n'
                                      ' op <= "001"; end;', "op"), {"001"})

    def test_cpus_do_repositorio(self):
        """A regra acusa a reduzida_4 (defeito real) e nenhuma CPU aprovada."""
        exp = REPO_ROOT / "experimentos"
        if not (exp / "luna6_abl_m_reduzida_4").is_dir():
            self.skipTest("experimentos nao versionados nesta copia")
        falha = itf.problemas(itf.checar_cpu(exp / "luna6_abl_m_reduzida_4"))
        self.assertEqual([(l.sinal, sorted(l.sem_decodificacao)) for l in falha],
                         [("alu_op", ["10010", "10011", "10100", "10101", "10110"])])
        for nome in ("luna6_prof_3", "luna6_evolui_im_5", "carbon4_evolui_im_1",
                     "luna6_abl_m_reduzida_2", "sonnet55_evolui_im_2"):
            self.assertEqual(itf.problemas(itf.checar_cpu(exp / nome)), [], nome)


if __name__ == "__main__":
    unittest.main()
