-- =============================================================================
-- register_file.vhd -- 32 x 32-bit general purpose registers
-- REQ: FR-02, FR-05
--
-- Two asynchronous read ports and one synchronous write port -- the minimum
-- that sustains one R-type instruction per cycle (NFR-02) without paying for
-- ports only a superscalar machine would use (NFR-01).
--
-- x0 is hardwired to zero: reads return 0 and writes are discarded (FR-02).
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity register_file is
    port (
        clk          : in  std_logic;
        rst          : in  std_logic;
        rs1_addr     : in  std_logic_vector(4 downto 0);
        rs2_addr     : in  std_logic_vector(4 downto 0);
        rd_addr      : in  std_logic_vector(4 downto 0);
        rd_data      : in  word_t;
        write_enable : in  std_logic;
        rs1_data     : out word_t;
        rs2_data     : out word_t
    );
end entity register_file;

architecture rtl of register_file is
    type reg_array_t is array (0 to 31) of word_t;
    signal regs : reg_array_t := (others => (others => '0'));
begin

    -- REQ: FR-02 -- asynchronous reads, x0 always zero
    rs1_data <= (others => '0') when rs1_addr = "00000"
                else regs(to_integer(unsigned(rs1_addr)));
    rs2_data <= (others => '0') when rs2_addr = "00000"
                else regs(to_integer(unsigned(rs2_addr)));

    -- REQ: FR-02, FR-09 -- synchronous write; write to x0 discarded
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                regs <= (others => (others => '0'));
            elsif write_enable = '1' and rd_addr /= "00000" then
                regs(to_integer(unsigned(rd_addr))) <= rd_data;
            end if;
        end if;
    end process;

end architecture rtl;
