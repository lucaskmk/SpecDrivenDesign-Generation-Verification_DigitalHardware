-- Project      : SpecHDL / trilha RISC-V -- exemplo "CPU escrita do zero"
-- File         : mono_regfile.vhd
-- Description  : RISC-V register file x0..x31 for the single-cycle core.
--                Two asynchronous read ports, one synchronous write port.
--
-- REQ: FR-RV-04, FR-RV-06, FR-RV-15
--
-- Design notes
-- ------------
-- 1. WRITE EDGE. Unlike the 5-stage pipeline core, which writes on the FALLING
--    edge to dodge a data hazard, this core writes on the RISING edge -- the
--    same edge that advances the PC and commits the data RAM. In a single-cycle
--    machine every value read in a cycle is produced by the state that existed
--    at the start of that cycle, so there is no hazard to dodge and no reason
--    to use half a clock period.
--
-- 2. STORAGE SHAPE. `registers` is a 1-D array of 32-bit words on purpose: the
--    GHDL VPI does not expose multi-dimensional arrays to cocotb, so anything a
--    testbench must read back has to be 1-D (specs/decisions.md, ADR-002).
--    The conformance manifest points `[observe] registers` at this signal.
--
-- 3. x0. Hardwired to zero on BOTH sides: reads of index 0 return zero and
--    writes to index 0 are discarded, so x0 stays zero even if a program
--    targets it (FR-RV-04).

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;


entity mono_regfile is
    port(
        clk         : in  std_logic;
        rst         : in  std_logic;                        -- asynchronous, active high

        rs1_select  : in  std_logic_vector(4 downto 0);
        rs2_select  : in  std_logic_vector(4 downto 0);
        rd_select   : in  std_logic_vector(4 downto 0);
        rd_data     : in  std_logic_vector(31 downto 0);
        write_rd    : in  std_logic;

        rs1         : out std_logic_vector(31 downto 0);
        rs2         : out std_logic_vector(31 downto 0)
    );
end mono_regfile;


architecture Behavioral of mono_regfile is

    -- 1-D array of words: required for cocotb observability (ADR-002)
    type REGISTER_ARRAY_t is array(0 to 31) of std_logic_vector(31 downto 0);
    signal registers : REGISTER_ARRAY_t := (others => (others => '0'));

    signal rs1_index : integer range 0 to 31 := 0;
    signal rs2_index : integer range 0 to 31 := 0;
    signal rd_index  : integer range 0 to 31 := 0;

begin

    rs1_index <= to_integer(unsigned(rs1_select));
    rs2_index <= to_integer(unsigned(rs2_select));
    rd_index  <= to_integer(unsigned(rd_select));

    -- asynchronous reads; x0 always reads zero
    rs1 <= (others => '0') when rs1_index = 0 else registers(rs1_index);
    rs2 <= (others => '0') when rs2_index = 0 else registers(rs2_index);

    -- synchronous write, asynchronous reset
    process(clk, rst)
    begin
        if rst = '1' then
            registers <= (others => (others => '0'));
        elsif rising_edge(clk) then
            if write_rd = '1' and rd_index /= 0 then
                registers(rd_index) <= rd_data;
            end if;
        end if;
    end process;

end Behavioral;
