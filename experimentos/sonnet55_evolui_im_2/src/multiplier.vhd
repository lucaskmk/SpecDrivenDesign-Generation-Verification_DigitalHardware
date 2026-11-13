library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity multiplier is
    port(
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        op : in std_logic_vector(1 downto 0);
        result : out std_logic_vector(31 downto 0)
    );
end multiplier;

architecture rtl of multiplier is
    signal a_ext   : signed(32 downto 0);
    signal b_ext   : signed(32 downto 0);
    signal product : signed(65 downto 0);
begin

    -- Operand extension to 33 bits depending on the selected operation
    process(operand_a, operand_b, op)
    begin
        -- operand_a: signed for MUL, MULH, MULHSU; unsigned for MULHU
        if op = "11" then
            a_ext <= signed(resize(unsigned(operand_a), 33));
        else
            a_ext <= resize(signed(operand_a), 33);
        end if;

        -- operand_b: signed for MUL, MULH; unsigned for MULHSU, MULHU
        if op = "10" or op = "11" then
            b_ext <= signed(resize(unsigned(operand_b), 33));
        else
            b_ext <= resize(signed(operand_b), 33);
        end if;
    end process;

    product <= a_ext * b_ext;

    -- Slice selection: low word for MUL, high word otherwise
    process(product, op)
    begin
        if op = "00" then
            result <= std_logic_vector(product(31 downto 0));
        else
            result <= std_logic_vector(product(63 downto 32));
        end if;
    end process;

end rtl;
