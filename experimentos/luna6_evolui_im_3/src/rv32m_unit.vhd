library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity rv32m_unit is
    port(
        instr     : in  std_logic_vector(31 downto 0);
        operand_a : in  std_logic_vector(31 downto 0);
        operand_b : in  std_logic_vector(31 downto 0);
        valid     : out std_logic;
        result    : out std_logic_vector(31 downto 0)
    );
end entity rv32m_unit;

architecture rtl of rv32m_unit is
begin
    process(all)
        variable product_unsigned : unsigned(63 downto 0);
        variable product_signed   : signed(63 downto 0);
        variable product_signed_unsigned : signed(65 downto 0);
    begin
        valid  <= '0';
        result <= (others => '0');

        if instr(6 downto 0) = "0110011" and
           instr(31 downto 25) = "0000001" then
            case instr(14 downto 12) is
                when "000" =>
                    valid <= '1';
                    product_unsigned := unsigned(operand_a) * unsigned(operand_b);
                    result <= std_logic_vector(product_unsigned(31 downto 0));

                when "001" =>
                    valid <= '1';
                    product_signed := signed(operand_a) * signed(operand_b);
                    result <= std_logic_vector(product_signed(63 downto 32));

                when "010" =>
                    valid <= '1';
                    product_signed_unsigned :=
                        resize(signed(operand_a), 33) *
                        signed(resize(unsigned(operand_b), 33));
                    result <= std_logic_vector(product_signed_unsigned(63 downto 32));

                when "011" =>
                    valid <= '1';
                    product_unsigned := unsigned(operand_a) * unsigned(operand_b);
                    result <= std_logic_vector(product_unsigned(63 downto 32));

                when "100" =>
                    valid <= '1';
                    if operand_b = x"00000000" then
                        result <= x"FFFFFFFF";
                    elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                        result <= x"80000000";
                    else
                        result <= std_logic_vector(signed(operand_a) / signed(operand_b));
                    end if;

                when "101" =>
                    valid <= '1';
                    if operand_b = x"00000000" then
                        result <= x"FFFFFFFF";
                    else
                        result <= std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                    end if;

                when "110" =>
                    valid <= '1';
                    if operand_b = x"00000000" then
                        result <= operand_a;
                    elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                        result <= x"00000000";
                    else
                        result <= std_logic_vector(signed(operand_a) rem signed(operand_b));
                    end if;

                when "111" =>
                    valid <= '1';
                    if operand_b = x"00000000" then
                        result <= operand_a;
                    else
                        result <= std_logic_vector(unsigned(operand_a) rem unsigned(operand_b));
                    end if;

                when others =>
                    null;
            end case;
        end if;
    end process;
end architecture rtl;
