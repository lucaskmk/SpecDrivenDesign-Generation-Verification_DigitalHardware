-- =============================================================================
-- load_store_unit.vhd -- alignment, extension and byte enables for load/store
-- REQ: FR-06, FR-07
--
-- Combinational block, deliberately separate from the memory arrays: this is
-- what keeps data_ram_inst a direct child of the top level, which is the RAM
-- read-out contract of the verification interface (FR-10, pipeline:FR-17).
-- It also concentrates the alignment and out-of-range rule of FR-07 in one
-- place instead of spreading it over ROM and RAM.
--
-- funct3 encoding (RISC-V): (1 downto 0) = width (00 byte, 01 half, 10 word),
-- bit 2 = zero-extend flag on loads (lbu/lhu).
--
-- Byte/halfword selection is written as explicit case statements over the two
-- address LSBs instead of a slice with computed bounds: a dynamic slice range
-- simulates but is fragile in synthesis, and phase 5 has to synthesise the
-- very same sources that were verified.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity load_store_unit is
    port (
        addr             : in  word_t;
        funct3           : in  std_logic_vector(2 downto 0);
        mem_write        : in  std_logic;
        store_data       : in  word_t;  -- rs2
        ram_data         : in  word_t;
        ram_valid        : in  std_logic;
        rom_data         : in  word_t;
        rom_valid        : in  std_logic;
        ram_write_enable : out std_logic;
        ram_byte_enable  : out std_logic_vector(3 downto 0);
        ram_data_in      : out word_t;
        load_result      : out word_t
    );
end entity load_store_unit;

architecture rtl of load_store_unit is
    signal aligned  : std_logic;
    signal in_range : std_logic;
    signal src_word : word_t;
    signal byte_v   : std_logic_vector(7 downto 0);
    signal half_v   : std_logic_vector(15 downto 0);
begin

    -- REQ: FR-01, FR-07 -- alignment rule per access width
    aligned <= '1' when (funct3(1 downto 0) = "00")
                     or (funct3(1 downto 0) = "01" and addr(0) = '0')
                     or (funct3(1 downto 0) = "10" and addr(1 downto 0) = "00")
               else '0';

    in_range <= ram_valid or rom_valid;

    -- REQ: FR-06 -- ROM wins the mux: the two regions never overlap
    src_word <= rom_data when rom_valid = '1' else ram_data;

    -- REQ: FR-01 -- little-endian byte/halfword selection inside the word
    with addr(1 downto 0) select byte_v <=
        src_word(7 downto 0)    when "00",
        src_word(15 downto 8)   when "01",
        src_word(23 downto 16)  when "10",
        src_word(31 downto 24)  when others;

    half_v <= src_word(15 downto 0) when addr(1) = '0' else src_word(31 downto 16);

    -- ---------------------------------------------------------------------
    -- Load path -- REQ: FR-07
    -- ---------------------------------------------------------------------
    process (funct3, src_word, byte_v, half_v, aligned, in_range)
    begin
        if aligned = '0' or in_range = '0' then
            -- REQ: FR-07 -- misaligned or out-of-range read
            load_result <= INVALID_READ;
        else
            case funct3 is
                when "000" =>  -- lb, sign extended
                    load_result <= (31 downto 8 => byte_v(7)) & byte_v;
                when "100" =>  -- lbu, zero extended
                    load_result <= (31 downto 8 => '0') & byte_v;
                when "001" =>  -- lh, sign extended
                    load_result <= (31 downto 16 => half_v(15)) & half_v;
                when "101" =>  -- lhu, zero extended
                    load_result <= (31 downto 16 => '0') & half_v;
                when "010" =>  -- lw
                    load_result <= src_word;
                when others =>
                    -- funct3 = 011/110/111 is not an RV32I load (FR-14); the
                    -- control unit already blocks the register write.
                    load_result <= INVALID_READ;
            end case;
        end if;
    end process;

    -- ---------------------------------------------------------------------
    -- Store path -- REQ: FR-07
    -- ---------------------------------------------------------------------
    process (funct3, store_data, addr)
        variable be : std_logic_vector(3 downto 0);
        variable dw : word_t;
    begin
        be := "0000";
        dw := (others => '0');

        case funct3(1 downto 0) is
            when "00" =>  -- sb: one byte lane, data replicated into it
                case addr(1 downto 0) is
                    when "00" => be := "0001"; dw(7 downto 0)   := store_data(7 downto 0);
                    when "01" => be := "0010"; dw(15 downto 8)  := store_data(7 downto 0);
                    when "10" => be := "0100"; dw(23 downto 16) := store_data(7 downto 0);
                    when others => be := "1000"; dw(31 downto 24) := store_data(7 downto 0);
                end case;
            when "01" =>  -- sh: two byte lanes
                if addr(1) = '0' then
                    be := "0011";
                    dw(15 downto 0) := store_data(15 downto 0);
                else
                    be := "1100";
                    dw(31 downto 16) := store_data(15 downto 0);
                end if;
            when "10" =>  -- sw
                be := "1111";
                dw := store_data;
            when others =>
                be := "0000";
        end case;

        ram_byte_enable <= be;
        ram_data_in     <= dw;
    end process;

    -- REQ: FR-07 -- a store outside the RAM range (including the read-only
    -- ROM range) or misaligned is silently discarded
    ram_write_enable <= mem_write and ram_valid and aligned;

end architecture rtl;
