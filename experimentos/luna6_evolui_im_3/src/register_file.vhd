library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity register_file is
    port(
        clk : in std_logic;
        rst : in std_logic;
        rs1_addr : in std_logic_vector(4 downto 0);
        rs2_addr : in std_logic_vector(4 downto 0);
        rs1_data : out std_logic_vector(31 downto 0);
        rs2_data : out std_logic_vector(31 downto 0);
        rd_addr : in std_logic_vector(4 downto 0);
        rd_data : in std_logic_vector(31 downto 0);
        rd_write : in std_logic
    );
end entity register_file;

architecture rtl of register_file is
    type register_array_t is array (0 to 31) of std_logic_vector(31 downto 0);
    signal registers : register_array_t;
begin
    process(clk, rst)
    begin
        if rst = '1' then
            for i in registers'range loop
                registers(i) <= (others => '0');
            end loop;
        elsif rising_edge(clk) then
            if rd_write = '1' and rd_addr /= "00000" then
                registers(to_integer(unsigned(rd_addr))) <= rd_data;
            end if;
        end if;
    end process;

    process(all)
    begin
        rs1_data <= (others => '0');
        rs2_data <= (others => '0');

        if rst /= '1' then
            if rs1_addr /= "00000" then
                rs1_data <= registers(to_integer(unsigned(rs1_addr)));
            end if;

            if rs2_addr /= "00000" then
                rs2_data <= registers(to_integer(unsigned(rs2_addr)));
            end if;
        end if;
    end process;
end architecture rtl;
