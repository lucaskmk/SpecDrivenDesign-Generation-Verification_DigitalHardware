library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity immediate_generator is
    port(
        instr : in std_logic_vector(31 downto 0);
        imm_i : out std_logic_vector(31 downto 0);
        imm_s : out std_logic_vector(31 downto 0);
        imm_b : out std_logic_vector(31 downto 0);
        imm_u : out std_logic_vector(31 downto 0);
        imm_j : out std_logic_vector(31 downto 0)
    );
end immediate_generator;

architecture rtl of immediate_generator is
begin
    imm_i <= std_logic_vector(resize(signed(instr(31 downto 20)), 32));
    imm_s <= std_logic_vector(resize(signed(instr(31 downto 25) & instr(11 downto 7)), 32));
    imm_b <= std_logic_vector(resize(signed(instr(31) & instr(7) & instr(30 downto 25) & instr(11 downto 8) & '0'), 32));
    imm_u <= instr(31 downto 12) & "000000000000";
    imm_j <= std_logic_vector(resize(signed(instr(31) & instr(19 downto 12) & instr(20) & instr(30 downto 21) & '0'), 32));
end rtl;
