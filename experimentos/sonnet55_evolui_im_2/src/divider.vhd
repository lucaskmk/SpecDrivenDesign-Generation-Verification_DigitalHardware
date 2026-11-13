library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity divider is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        is_signed : in std_logic;
        want_rem : in std_logic;
        result : out std_logic_vector(31 downto 0)
    );
end divider;

architecture rtl of divider is
begin
    process(operand_a, operand_b, is_signed, want_rem)
        variable ua : unsigned(31 downto 0);
        variable ub : unsigned(31 downto 0);
        variable sa : signed(31 downto 0);
        variable sb : signed(31 downto 0);
        variable res : std_logic_vector(31 downto 0);
    begin
        ua := unsigned(operand_a);
        ub := unsigned(operand_b);
        sa := signed(operand_a);
        sb := signed(operand_b);
        res := (others => '0');

        if ub = 0 then
            if want_rem = '1' then
                res := operand_a;
            else
                res := (others => '1');
            end if;
        elsif is_signed = '1' and operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
            if want_rem = '1' then
                res := (others => '0');
            else
                res := x"80000000";
            end if;
        elsif is_signed = '1' then
            if want_rem = '1' then
                res := std_logic_vector(sa rem sb);
            else
                res := std_logic_vector(sa / sb);
            end if;
        else
            if want_rem = '1' then
                res := std_logic_vector(ua rem ub);
            else
                res := std_logic_vector(ua / ub);
            end if;
        end if;

        result <= res;
    end process;
end rtl;
