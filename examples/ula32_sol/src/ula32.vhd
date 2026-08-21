-- 32-bit MIPS-style arithmetic logic unit.
-- REQ: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, NFR-01, NFR-02

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity ula32 is
    port (
        a           : in  std_logic_vector(31 downto 0);
        b           : in  std_logic_vector(31 downto 0);
        alu_control : in  std_logic_vector(3 downto 0);
        result      : out std_logic_vector(31 downto 0);
        zero        : out std_logic
    );
end entity ula32;

architecture rtl of ula32 is
begin
    process (a, b, alu_control)
        variable next_result : std_logic_vector(31 downto 0);
    begin
        case alu_control is
            when "0000" =>
                next_result := a and b;
            when "0001" =>
                next_result := a or b;
            when "0010" =>
                next_result := std_logic_vector(unsigned(a) + unsigned(b));
            when "0110" =>
                next_result := std_logic_vector(unsigned(a) - unsigned(b));
            when "0111" =>
                next_result := (others => '0');
                if signed(a) < signed(b) then
                    next_result(0) := '1';
                end if;
            when "1100" =>
                next_result := not (a or b);
            when others =>
                next_result := (others => '0');
        end case;

        result <= next_result;
        if next_result = x"00000000" then
            zero <= '1';
        else
            zero <= '0';
        end if;
    end process;
end architecture rtl;
