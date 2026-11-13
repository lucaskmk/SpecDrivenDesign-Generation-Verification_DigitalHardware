library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity m_unit is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        funct3    : in std_logic_vector(2 downto 0);
        result    : out std_logic_vector(31 downto 0)
    );
end entity m_unit;

architecture rtl of m_unit is
begin
    process(all)
        variable signed_product   : signed(63 downto 0);
        variable unsigned_product : unsigned(63 downto 0);
        variable mixed_product    : signed(65 downto 0);
    begin
        result <= (others => '0');

        case funct3 is
            when "000" =>
                signed_product := signed(operand_a) * signed(operand_b);
                result <= std_logic_vector(signed_product(31 downto 0));

            when "001" =>
                signed_product := signed(operand_a) * signed(operand_b);
                result <= std_logic_vector(signed_product(63 downto 32));

            when "010" =>
                mixed_product :=
                    resize(signed(operand_a), 33) * signed('0' & operand_b);
                result <= std_logic_vector(mixed_product(63 downto 32));

            when "011" =>
                unsigned_product := unsigned(operand_a) * unsigned(operand_b);
                result <= std_logic_vector(unsigned_product(63 downto 32));

            when "100" =>
                if operand_b = x"00000000" then
                    result <= x"FFFFFFFF";
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result <= x"80000000";
                else
                    result <= std_logic_vector(signed(operand_a) / signed(operand_b));
                end if;

            when "101" =>
                if operand_b = x"00000000" then
                    result <= x"FFFFFFFF";
                else
                    result <= std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                end if;

            when "110" =>
                if operand_b = x"00000000" then
                    result <= operand_a;
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result <= x"00000000";
                else
                    result <= std_logic_vector(signed(operand_a) rem signed(operand_b));
                end if;

            when "111" =>
                if operand_b = x"00000000" then
                    result <= operand_a;
                else
                    result <= std_logic_vector(unsigned(operand_a) rem unsigned(operand_b));
                end if;

            when others =>
                null;
        end case;
    end process;
end architecture rtl;
