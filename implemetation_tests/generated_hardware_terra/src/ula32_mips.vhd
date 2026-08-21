library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

-- REQ: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-09, NFR-01, NFR-02
entity ula32_mips is
    port (
        a           : in  std_logic_vector(31 downto 0);
        b           : in  std_logic_vector(31 downto 0);
        alu_control : in  std_logic_vector(3 downto 0);
        result      : out std_logic_vector(31 downto 0);
        zero        : out std_logic
    );
end entity ula32_mips;

architecture rtl of ula32_mips is
    signal result_internal : std_logic_vector(31 downto 0);
begin
    process (a, b, alu_control)
    begin
        case alu_control is
            when "0000" => result_internal <= a and b;
            when "0001" => result_internal <= a or b;
            when "0010" => result_internal <= std_logic_vector(unsigned(a) + unsigned(b));
            when "0110" => result_internal <= std_logic_vector(unsigned(a) - unsigned(b));
            when "0111" =>
                if signed(a) < signed(b) then
                    result_internal <= x"00000001";
                else
                    result_internal <= (others => '0');
                end if;
            when "1100" => result_internal <= a nor b;
            when others => result_internal <= (others => '0');
        end case;
    end process;

    result <= result_internal;
    zero <= '1' when result_internal = x"00000000" else '0';
end architecture rtl;
