-- REQ: FR-RV-06 (observable state)
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity register_file is
    port(
        clk             : in std_logic;
        rst             : in std_logic; -- synchronous reset, ACTIVE LOW
        reg_write_enable  : in std_logic;
        write_register  : in std_logic_vector(4 downto 0);
        read_register1  : in std_logic_vector(4 downto 0);
        read_register2  : in std_logic_vector(4 downto 0);
        data_in         : in std_logic_vector(31 downto 0);
        data_out1       : out std_logic_vector(31 downto 0);
        data_out2       : out std_logic_vector(31 downto 0)
    );
end register_file;

architecture Behavioral of register_file is
    type reg_array_t is array (0 to 31) of std_logic_vector(31 downto 0);
    signal registers : reg_array_t := (others => (others => '0'));
begin

    -- Write operation with synchronous reset
    process(clk, rst)
    begin
        if rst = '0' then -- Active LOW reset
            for i in 0 to 31 loop
                registers(i) <= (others => '0');
            end loop;
        elsif rising_edge(clk) then
            if reg_write_enable = '1' and write_register /= "00000" then
                registers(to_integer(unsigned(write_register))) <= data_in;
            end if;
        end if;
    end process;

    -- Read operations (combinational)
    data_out1 <= registers(to_integer(unsigned(read_register1)));
    data_out2 <= registers(to_integer(unsigned(read_register2)));

end Behavioral;
