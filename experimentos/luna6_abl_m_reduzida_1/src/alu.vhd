library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity alu is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        alu_op : in std_logic_vector(3 downto 0);
        result : out std_logic_vector(31 downto 0);
        compare_equal : out std_logic;
        compare_signed_less : out std_logic;
        compare_unsigned_less : out std_logic
    );
end alu;

architecture rtl of alu is
begin
    process(all)
        variable r : std_logic_vector(31 downto 0);
        variable product_signed : signed(127 downto 0);
        variable product_mixed : signed(127 downto 0);
        variable product_unsigned : unsigned(127 downto 0);
        variable shift_amount : natural range 0 to 31;
    begin
        r := (others => '0');

        if operand_a = operand_b then
            compare_equal <= '1';
        else
            compare_equal <= '0';
        end if;

        if signed(operand_a) < signed(operand_b) then
            compare_signed_less <= '1';
        else
            compare_signed_less <= '0';
        end if;

        if unsigned(operand_a) < unsigned(operand_b) then
            compare_unsigned_less <= '1';
        else
            compare_unsigned_less <= '0';
        end if;

        shift_amount := to_integer(unsigned(operand_b(4 downto 0)));

        case alu_op is
            when "0000" =>
                r := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));

            when "0001" =>
                r := std_logic_vector(unsigned(operand_a) - unsigned(operand_b));

            when "0010" =>
                r := std_logic_vector(shift_left(unsigned(operand_a), shift_amount));

            when "0011" =>
                r := std_logic_vector(shift_right(unsigned(operand_a), shift_amount));

            when "0100" =>
                r := std_logic_vector(shift_right(signed(operand_a), shift_amount));

            when "0101" =>
                r := operand_a xor operand_b;

            when "0110" =>
                r := operand_a or operand_b;

            when "0111" =>
                r := operand_a and operand_b;

            when "1000" =>
                product_unsigned :=
                    unsigned(resize(unsigned(operand_a), 64)) *
                    unsigned(resize(unsigned(operand_b), 64));
                r := std_logic_vector(product_unsigned(31 downto 0));

            when "1001" =>
                product_signed :=
                    signed(resize(signed(operand_a), 64)) *
                    signed(resize(signed(operand_b), 64));
                r := std_logic_vector(product_signed(63 downto 32));

            when "1010" =>
                product_mixed :=
                    signed(resize(signed(operand_a), 64)) *
                    signed(resize(unsigned(operand_b), 64));
                r := std_logic_vector(product_mixed(63 downto 32));

            when "1011" =>
                product_unsigned :=
                    unsigned(resize(unsigned(operand_a), 64)) *
                    unsigned(resize(unsigned(operand_b), 64));
                r := std_logic_vector(product_unsigned(63 downto 32));

            when "1100" =>
                if operand_b = x"00000000" then
                    r := (others => '1');
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    r := x"80000000";
                else
                    r := std_logic_vector(signed(operand_a) / signed(operand_b));
                end if;

            when "1101" =>
                if operand_b = x"00000000" then
                    r := (others => '1');
                else
                    r := std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                end if;

            when "1110" =>
                if operand_b = x"00000000" then
                    r := operand_a;
                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                    r := x"00000000";
                else
                    r := std_logic_vector(signed(operand_a) rem signed(operand_b));
                end if;

            when "1111" =>
                if operand_b = x"00000000" then
                    r := operand_a;
                else
                    r := std_logic_vector(unsigned(operand_a) rem unsigned(operand_b));
                end if;

            when others =>
                r := (others => '0');
        end case;

        result <= r;
    end process;
end rtl;
