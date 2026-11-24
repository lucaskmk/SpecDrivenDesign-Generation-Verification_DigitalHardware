library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity alu is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        alu_op : in std_logic_vector(4 downto 0);
        result : out std_logic_vector(31 downto 0);
        equal : out std_logic;
        signed_less : out std_logic;
        unsigned_less : out std_logic
    );
end alu;

architecture rtl of alu is
begin
    process(operand_a, operand_b, alu_op)
        variable result_v : std_logic_vector(31 downto 0);
        variable product_ss : signed(63 downto 0);
        variable product_su : signed(65 downto 0);
        variable product_uu : unsigned(63 downto 0);
        variable shift_amount : natural range 0 to 31;
    begin
        result_v := (others => '0');

        if operand_a = operand_b then
            equal <= '1';
        else
            equal <= '0';
        end if;

        if signed(operand_a) < signed(operand_b) then
            signed_less <= '1';
        else
            signed_less <= '0';
        end if;

        if unsigned(operand_a) < unsigned(operand_b) then
            unsigned_less <= '1';
        else
            unsigned_less <= '0';
        end if;

        shift_amount := to_integer(unsigned(operand_b(4 downto 0)));

        case alu_op is
            when "00000" =>
                result_v := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));

            when "00001" =>
                result_v := std_logic_vector(unsigned(operand_a) - unsigned(operand_b));

            when "00010" =>
                result_v := std_logic_vector(shift_left(unsigned(operand_a), shift_amount));

            when "00011" =>
                if signed(operand_a) < signed(operand_b) then
                    result_v := x"00000001";
                end if;

            when "00100" =>
                if unsigned(operand_a) < unsigned(operand_b) then
                    result_v := x"00000001";
                end if;

            when "00101" =>
                result_v := operand_a xor operand_b;

            when "00110" =>
                result_v := std_logic_vector(shift_right(unsigned(operand_a), shift_amount));

            when "00111" =>
                result_v := std_logic_vector(shift_right(signed(operand_a), shift_amount));

            when "01000" =>
                result_v := operand_a or operand_b;

            when "01001" =>
                result_v := operand_a and operand_b;

            when "01010" =>
                product_uu := unsigned(operand_a) * unsigned(operand_b);
                result_v := std_logic_vector(product_uu(31 downto 0));

            when "01011" =>
                product_ss := signed(operand_a) * signed(operand_b);
                result_v := std_logic_vector(product_ss(63 downto 32));

            when "01100" =>
                product_su := resize(signed(operand_a), 33) *
                              signed('0' & operand_b);
                result_v := std_logic_vector(product_su(63 downto 32));

            when "01101" =>
                product_uu := unsigned(operand_a) * unsigned(operand_b);
                result_v := std_logic_vector(product_uu(63 downto 32));

            when "01110" =>
                if operand_b = x"00000000" then
                    result_v := x"FFFFFFFF";
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result_v := x"80000000";
                else
                    result_v := std_logic_vector(signed(operand_a) / signed(operand_b));
                end if;

            when "01111" =>
                if operand_b = x"00000000" then
                    result_v := x"FFFFFFFF";
                else
                    result_v := std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                end if;

            when "10000" =>
                if operand_b = x"00000000" then
                    result_v := operand_a;
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    result_v := x"00000000";
                else
                    result_v := std_logic_vector(signed(operand_a) rem signed(operand_b));
                end if;

            when "10001" =>
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
end rtl;
