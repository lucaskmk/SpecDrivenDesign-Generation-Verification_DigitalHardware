library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity alu is
    port(
        operand_a   : in  std_logic_vector(31 downto 0);
        operand_b   : in  std_logic_vector(31 downto 0);
        alu_control : in  std_logic_vector(3 downto 0);
        result      : out std_logic_vector(31 downto 0);
        equal       : out std_logic;
        signed_less : out std_logic;
        unsigned_less : out std_logic
    );
end entity alu;

architecture rtl of alu is
begin
    process(all)
        variable result_value : std_logic_vector(31 downto 0);
    begin
        result_value := (others => '0');

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

        case alu_control is
            when "0000" =>
                result_value := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));
            when "0001" =>
                result_value := std_logic_vector(unsigned(operand_a) - unsigned(operand_b));
            when "0010" =>
                result_value := operand_a and operand_b;
            when "0011" =>
                result_value := operand_a or operand_b;
            when "0100" =>
                result_value := operand_a xor operand_b;
            when "0101" =>
                result_value := std_logic_vector(shift_left(unsigned(operand_a), to_integer(unsigned(operand_b(4 downto 0)))));
            when "0110" =>
                result_value := std_logic_vector(shift_right(unsigned(operand_a), to_integer(unsigned(operand_b(4 downto 0)))));
            when "0111" =>
                result_value := std_logic_vector(shift_right(signed(operand_a), to_integer(unsigned(operand_b(4 downto 0)))));
            when "1000" =>
                if signed(operand_a) < signed(operand_b) then
                    result_value := x"00000001";
                end if;
            when "1001" =>
                if unsigned(operand_a) < unsigned(operand_b) then
                    result_value := x"00000001";
                end if;
            when others =>
                null;
        end case;

        result <= result_value;
    end process;
end architecture rtl;
