-- =============================================================================
-- instruction_rom.vhd -- instruction ROM with a second read port for .rodata
-- REQ: FR-06, FR-07, FR-13
--
-- 1024 words mapped at 0x00000000. Port 1 feeds the fetch stage, port 2 lets
-- a load read constants placed in .rodata by the linker (mandatory in the
-- base test program: auipc/lui + offset). Both reads are asynchronous, which
-- is what makes CPI = 1 possible in a single-cycle datapath (NFR-02).
--
-- The ROM contents come from rom_image_pkg.vhd, generated from the program
-- .rm by phase 3b -- never hand written (FR-13).
--
-- Read-only by construction: there is no write port, so a store that lands in
-- the ROM range is silently discarded (FR-07).
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;
use work.rom_image_pkg.all;

entity instruction_rom is
    port (
        -- fetch port
        instr_addr : in  word_t;
        instr_out  : out word_t;
        -- data port (.rodata reads)
        data_addr  : in  word_t;
        data_out   : out word_t;
        data_valid : out std_logic  -- '1' when data_addr falls inside the ROM
    );
end entity instruction_rom;

architecture rtl of instruction_rom is
    -- Only the low 12 bits index the array (the region is 4 KB aligned), so
    -- the index can never leave the array bounds even for a wild address.
    signal instr_index : integer range 0 to ROM_SIZE_WORDS - 1;
    signal data_index  : integer range 0 to ROM_SIZE_WORDS - 1;
begin

    instr_index <= to_integer(unsigned(instr_addr(11 downto 2)));
    data_index  <= to_integer(unsigned(data_addr(11 downto 2)));

    -- REQ: FR-06, FR-13 -- fetch. Out of ROM range fetches read as all
    -- zeros, which the control unit decodes as an illegal instruction and
    -- treats as a nop (FR-14).
    instr_out <= ROM_IMAGE(instr_index) when instr_addr(31 downto 12) = ROM_TAG
                 else (others => '0');

    -- REQ: FR-06, FR-07 -- .rodata read port
    data_out   <= ROM_IMAGE(data_index);
    data_valid <= '1' when data_addr(31 downto 12) = ROM_TAG else '0';

end architecture rtl;
