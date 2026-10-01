-- src/register_file.vhd

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity register_file is
    port(
        clk         : in std_logic;
        rst         : in std_logic;
        rd_addr1    : in std_logic_vector(4 downto 0);
        rd_addr2    : in std_logic_vector(4 downto 0);
        wr_addr     : in std_logic_vector(4 downto 0);
        wr_data     : in std_logic_vector(31 downto 0);
        wr_en       : in std_logic;
        rd_data1    : out std_logic_vector(31 downto 0);
        rd_data2    : out std_logic_vector(31 downto 0)
    );
end register_file;

architecture Behavioral of register_file is
    type reg_array_t is array (0 to 31) of std_logic_vector(31 downto 0);
    signal registers : reg_array_t := (others => (others => '0'));
begin

    -- Read operations are combinational
    rd_data1 <= registers(to_integer(unsigned(rd_addr1))) when rd_addr1 /= "00000" else (others => '0');
    rd_data2 <= registers(to_integer(unsigned(rd_addr2))) when rd_addr2 /= "00000" else (others => '0');

    -- Write operation is sequential
    process(clk, rst)
    begin
        if rst = '1' then
            -- Reset all registers to 0 on active high reset
            for i in 0 to 31 loop
                registers(i) <= (others => '0');
            end loop;
        elsif rising_edge(clk) then
            if wr_en = '1' and wr_addr /= "00000" then
                -- Write data to the specified register address
                registers(to_integer(unsigned(wr_addr))) <= wr_data;
            end if;
        end if;
    end process;

end Behavioral;
