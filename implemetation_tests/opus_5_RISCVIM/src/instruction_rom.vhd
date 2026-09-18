-- =============================================================================
-- instruction_rom.vhd -- instruction ROM with a second read port for .rodata
-- REQ: FR-06, FR-07, FR-13
--
-- 1024 words mapped at 0x00000000. Port 1 feeds the fetch stage, port 2 lets
-- a load read constants placed in .rodata by the linker (mandatory in the
-- base test program: auipc/lui + offset). Both reads are asynchronous, which
-- is what makes CPI = 1 possible in a single-cycle datapath (NFR-02).
--
-- REQ: FR-13 -- the image is selected at ELABORATION by ROM_INIT_FILE:
--
--   ROM_INIT_FILE = ""      the image comes from rom_image_pkg.vhd, generated
--                           from the program .rm. This is the default, so the
--                           original behaviour and the synthesis path of
--                           phase 5 are preserved untouched (principle 8).
--
--   ROM_INIT_FILE = path    the image is read from a .ram file. That is what
--                           lets the conformance suite of the repository
--                           validator swap the program without editing VHDL
--                           (repo:FR-RV-08, repo:FR-RV-09).
--
-- Why elaboration and not runtime: cocotb cannot write to a ROM under GHDL --
-- the write is silently ignored (../../specs/decisions.md, ADR-003).
--
-- .ram image format (ADR-003), as produced by rvverify/asm.py:
--   * one 32-bit word per line, 8 hexadecimal digits, no 0x prefix, any case;
--   * line index 0 is byte address 0x00000000, line n is byte address 4*n;
--   * blank lines are ignored; '#' starts a comment up to end of line;
--   * words not present in the file read as 0x00000000.
--
-- Read-only by construction: there is no write port, so a store that lands in
-- the ROM range is silently discarded (FR-07).
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use std.textio.all;
use work.cpu_pkg.all;
use work.rom_image_pkg.all;

entity instruction_rom is
    generic (
        -- "" keeps ROM_IMAGE from rom_image_pkg.vhd (FR-13, default path)
        ROM_INIT_FILE : string := ""
    );
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

    -- hexadecimal digit -> value, -1 when the character is not a hex digit
    function hex_digit (c : character) return integer is
    begin
        case c is
            when '0' to '9' => return character'pos(c) - character'pos('0');
            when 'a' to 'f' => return character'pos(c) - character'pos('a') + 10;
            when 'A' to 'F' => return character'pos(c) - character'pos('A') + 10;
            when others     => return -1;
        end case;
    end function;

    -- REQ: FR-13 -- builds the ROM contents at elaboration time.
    impure function load_rom return rom_image_t is
        variable m      : rom_image_t := (others => (others => '0'));
        file     f      : text;
        variable status : file_open_status;
        variable l      : line;
        variable acc    : unsigned(XLEN - 1 downto 0);
        variable digits : natural;
        variable hv     : integer;
        variable idx    : natural := 0;
        variable c      : character;
    begin
        if ROM_INIT_FILE = "" then
            return ROM_IMAGE;                    -- generated package (default)
        end if;

        file_open(status, f, ROM_INIT_FILE, read_mode);
        assert status = open_ok
            report "instruction_rom: cannot open .ram image: " & ROM_INIT_FILE
            severity failure;

        while not endfile(f) loop
            readline(f, l);
            acc    := (others => '0');
            digits := 0;
            if l /= null then
                for i in l.all'range loop
                    c := l.all(i);
                    exit when c = '#';                  -- comment to end of line
                    if c = ' ' or c = HT or c = CR then
                        exit when digits > 0;           -- end of the word
                    else
                        hv := hex_digit(c);
                        assert hv >= 0
                            report "instruction_rom: invalid character in .ram image ("
                                   & ROM_INIT_FILE & "): '" & c & "'"
                            severity failure;
                        assert digits < 8
                            report "instruction_rom: more than 8 hex digits on a line of "
                                   & ROM_INIT_FILE
                            severity failure;
                        acc    := acc(XLEN - 5 downto 0) & to_unsigned(hv, 4);
                        digits := digits + 1;
                    end if;
                end loop;
            end if;

            if digits > 0 then                          -- blank/comment: skipped
                assert idx < ROM_SIZE_WORDS
                    report "instruction_rom: the .ram image (" & ROM_INIT_FILE
                           & ") does not fit in ROM_SIZE_WORDS words"
                    severity failure;
                if idx < ROM_SIZE_WORDS then
                    m(idx) := std_logic_vector(acc);
                end if;
                idx := idx + 1;
            end if;
        end loop;

        file_close(f);
        return m;
    end function;

    constant IMAGE : rom_image_t := load_rom;

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
    instr_out <= IMAGE(instr_index) when instr_addr(31 downto 12) = ROM_TAG
                 else (others => '0');

    -- REQ: FR-06, FR-07 -- .rodata read port
    data_out   <= IMAGE(data_index);
    data_valid <= '1' when data_addr(31 downto 12) = ROM_TAG else '0';

end architecture rtl;
