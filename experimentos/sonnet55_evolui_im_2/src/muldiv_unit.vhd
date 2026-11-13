library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity muldiv_unit is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        funct3 : in std_logic_vector(2 downto 0);
        result : out std_logic_vector(31 downto 0)
    );
end muldiv_unit;

architecture rtl of muldiv_unit is
    component multiplier is
        port(
            operand_a : in std_logic_vector(31 downto 0);
            operand_b : in std_logic_vector(31 downto 0);
            op : in std_logic_vector(1 downto 0);
            result : out std_logic_vector(31 downto 0)
        );
    end component;

    component divider is
        port(
            operand_a : in std_logic_vector(31 downto 0);
            operand_b : in std_logic_vector(31 downto 0);
            is_signed : in std_logic;
            want_rem : in std_logic;
            result : out std_logic_vector(31 downto 0)
        );
    end component;

    signal mul_op     : std_logic_vector(1 downto 0);
    signal div_signed : std_logic;
    signal div_rem    : std_logic;
    signal mul_result : std_logic_vector(31 downto 0);
    signal div_result : std_logic_vector(31 downto 0);
begin
    mul_op     <= funct3(1 downto 0);
    div_signed <= not funct3(0);
    div_rem    <= funct3(1);

    u_mul : multiplier
        port map(
            operand_a => operand_a,
            operand_b => operand_b,
            op        => mul_op,
            result    => mul_result
        );

    u_div : divider
        port map(
            operand_a => operand_a,
            operand_b => operand_b,
            is_signed => div_signed,
            want_rem  => div_rem,
            result    => div_result
        );

    result <= mul_result when funct3(2) = '0' else div_result;
end rtl;
