library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity rv32m is
    port(
        operand_a : in  std_logic_vector(31 downto 0);
        operand_b : in  std_logic_vector(31 downto 0);
        funct3    : in  std_logic_vector(2 downto 0);
        result    : out std_logic_vector(31 downto 0)
    );
end entity rv32m;

architecture rtl of rv32m is
begin
    process(operand_a, operand_b, funct3)
        variable result_v : std_logic_vector(31 downto 0);
        variable product_u : unsigned(63 downto 0);
        variable product_ss : signed(63 downto 0);
        variable operand_a_ext : signed(32 downto 0);
        variable operand_b_ext : signed(32 downto 0);
        variable product_su : signed(65 downto 0);
    begin
        result_v := (others => '0');

        case funct3 is
            when "000" =>
                product_u := unsigned(operand_a) * unsigned(operand_b);
                result_v := std_logic_vector(product_u(31 downto 0));

            when "001" =>
                product_ss := signed(operand_a) * signed(operand_b);
                result_v := std_logic_vector(product_ss(63 downto 32));

            when "010" =>
                operand_a_ext := resize(signed(operand_a), 33);
                operand_b_ext := signed('0' & operand_b);
                product_su := operand_a_ext * operand_b_ext;
                result_v := std_logic_vector(product_su(63 downto 32));

            when "011" =>
                product_u := unsigned(operand_a) * unsigned(operand_b);
                result_v := std_logic_vector(product_u(63 downto 32));

            when "100" =>
                if operand_b = x"00000000" then
                    result_v := x"FFFFFFFF";
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result_v := x"80000000";
                else
                    result_v := std_logic_vector(signed(operand_a) / signed(operand_b));
                end if;

            when "101" =>
                if operand_b = x"00000000" then
                    result_v := x"FFFFFFFF";
                else
                    result_v := std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                end if;

            when "110" =>
                if operand_b = x"00000000" then
                    result_v := operand_a;
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result_v := x"00000000";
                else
                    result_v := std_logic_vector(signed(operand_a) rem signed(operand_b));
                end if;

            when "111" =>
                if operand_b = x"00000000" then
                    result_v := operand_a;
                else
                    result_v := std_logic_vector(unsigned(operand_a) rem unsigned(operand_b));
                end if;

            when others =>
                result_v := (others => '0');
        end case;

        result <= result_v;
    end process;
end architecture rtl;
