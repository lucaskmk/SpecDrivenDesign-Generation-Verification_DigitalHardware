library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity register_file is
    port(
        clk : in std_logic;
        rst : in std_logic;
        read_addr1 : in std_logic_vector(4 downto 0);
        read_addr2 : in std_logic_vector(4 downto 0);
        read_data1 : out std_logic_vector(31 downto 0);
        read_data2 : out std_logic_vector(31 downto 0);
        write_enable : in std_logic;
        write_addr : in std_logic_vector(4 downto 0);
        write_data : in std_logic_vector(31 downto 0)
    );
end register_file;

architecture rtl of register_file is
    type register_array_t is array (0 to 31) of std_logic_vector(31 downto 0);
    signal registers : register_array_t;
begin
    process(clk, rst)
    begin
        if rst = '1' then
            registers <= (others => (others => '0'));
        elsif rising_edge(clk) then
            if write_enable = '1' and write_addr /= "00000" then
                registers(to_integer(unsigned(write_addr))) <= write_data;
            end if;
        end if;
    end process;

    process(all)
    begin
        if rst = '1' then
            read_data1 <= (others => '0');
            read_data2 <= (others => '0');
        else
            if read_addr1 = "00000" then
                read_data1 <= (others => '0');
            else
                read_data1 <= registers(to_integer(unsigned(read_addr1)));
            end if;

            if read_addr2 = "00000" then
                read_data2 <= (others => '0');
            else
                read_data2 <= registers(to_integer(unsigned(read_addr2)));
            end if;
        end if;
    end process;
end rtl;
