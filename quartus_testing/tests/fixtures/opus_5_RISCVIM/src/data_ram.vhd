-- =============================================================================
-- data_ram.vhd -- data RAM (scratchpad), 1024 words at 0x00FC8000
-- REQ: FR-06, FR-07, FR-10
--
-- Asynchronous read, synchronous byte-enabled write. The storage is a 1-D
-- array of 32-bit words declared as a *signal* (not a variable) because the
-- verification testbench reads it through the GHDL VHPI as an indexable
-- array object -- that is the RAM read-out contract of the pipeline (FR-10,
-- repo:FR-RV-26). A process variable would not be visible to cocotb.
--
-- Byte lanes instead of the 2-D byte array of cpus/rv32i_pipeline: same sb/sh
-- semantics, but the word view is what the testbench can index directly.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity data_ram is
    port (
        clk          : in  std_logic;
        addr         : in  word_t;
        write_enable : in  std_logic;
        byte_enable  : in  std_logic_vector(3 downto 0);
        data_in      : in  word_t;
        data_out     : out word_t;
        addr_valid   : out std_logic  -- '1' when addr falls inside the RAM
    );
end entity data_ram;

architecture rtl of data_ram is
    -- REQ: FR-10 -- read by the cocotb testbench as data_ram_inst.memory
    signal memory : ram_array_t := (others => (others => '0'));

    -- 4 KB aligned region: the low 12 bits are the offset, so the index is
    -- always inside the array even for an address outside the RAM range.
    signal index : integer range 0 to RAM_SIZE_WORDS - 1;
    signal valid : std_logic;
begin

    index <= to_integer(unsigned(addr(11 downto 2)));
    valid <= '1' when addr(31 downto 12) = RAM_TAG else '0';

    addr_valid <= valid;
    data_out   <= memory(index);

    -- REQ: FR-06, FR-07 -- synchronous write, discarded outside the RAM range
    process (clk)
    begin
        if rising_edge(clk) then
            if write_enable = '1' and valid = '1' then
                if byte_enable(0) = '1' then
                    memory(index)(7 downto 0) <= data_in(7 downto 0);
                end if;
                if byte_enable(1) = '1' then
                    memory(index)(15 downto 8) <= data_in(15 downto 8);
                end if;
                if byte_enable(2) = '1' then
                    memory(index)(23 downto 16) <= data_in(23 downto 16);
                end if;
                if byte_enable(3) = '1' then
                    memory(index)(31 downto 24) <= data_in(31 downto 24);
                end if;
            end if;
        end if;
    end process;

end architecture rtl;
