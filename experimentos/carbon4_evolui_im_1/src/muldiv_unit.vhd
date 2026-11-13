library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity muldiv_unit is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        muldiv_op : in std_logic_vector(2 downto 0);
        result : out std_logic_vector(31 downto 0)
    );
end entity muldiv_unit;

architecture rtl of muldiv_unit is
begin
    comb_proc : process(operand_a, operand_b, muldiv_op)
        variable a_s : signed(31 downto 0);
        variable b_s : signed(31 downto 0);
        variable a_u : unsigned(31 downto 0);
        variable b_u : unsigned(31 downto 0);
        variable a_s33 : signed(32 downto 0);
        variable b_u33 : signed(32 downto 0);
        variable prod_ss : signed(63 downto 0);
        variable prod_uu : unsigned(63 downto 0);
        variable prod_su : signed(65 downto 0);
    begin
        result <= (others => '0');

        a_s := signed(operand_a);
        b_s := signed(operand_b);
        a_u := unsigned(operand_a);
        b_u := unsigned(operand_b);

        a_s33 := resize(a_s, 33);
        b_u33 := signed(resize(b_u, 33));

        prod_ss := a_s * b_s;
        prod_uu := a_u * b_u;
        prod_su := a_s33 * b_u33;

        case muldiv_op is
            when "000" => -- MUL
                result <= std_logic_vector(prod_uu(31 downto 0));

            when "001" => -- MULH
                result <= std_logic_vector(prod_ss(63 downto 32));

            when "010" => -- MULHSU
                result <= std_logic_vector(prod_su(63 downto 32));

            when "011" => -- MULHU
                result <= std_logic_vector(prod_uu(63 downto 32));

            when "100" => -- DIV
                if operand_b = x"00000000" then
                    result <= x"FFFFFFFF";
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result <= x"80000000";
                else
                    result <= std_logic_vector(a_s / b_s);
                end if;

            when "101" => -- DIVU
                if operand_b = x"00000000" then
                    result <= x"FFFFFFFF";
                else
                    result <= std_logic_vector(a_u / b_u);
                end if;

            when "110" => -- REM
                if operand_b = x"00000000" then
                    result <= operand_a;
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result <= x"00000000";
                else
                    result <= std_logic_vector(a_s rem b_s);
                end if;

            when "111" => -- REMU
                if operand_b = x"00000000" then
                    result <= operand_a;
                else
                    result <= std_logic_vector(a_u rem b_u);
                end if;

            when others =>
                result <= (others => '0');
        end case;
    end process comb_proc;
end architecture rtl;
