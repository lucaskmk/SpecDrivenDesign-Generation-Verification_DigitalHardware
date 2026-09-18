-- Project      : simple_RISCV_RV32I_vhdl
-- Author       : Morgan Demange <https://github.com/MorganDemange>
-- Date         : July 20, 2024
-- File         : instruction_memory.vhd

-- Description  :   Read-only memory containing the program instructions.
--                  Asynchronous module (no clock signal), outputs the 32-bit instruction stored at the given 32-bit input address.
--                  This memory uses little-endian storing. It is byte-addressable, however instructions must be aligned to 32-bit boundaries.
--
--                  The memory is mapped from address 0x00000000 to address (INSTRUCTION_MEMORY_SIZE_BYTES-1), both included.
--                  In case of an out-of-range or unaligned access, the output reads 0xffffffff.
--
-- Modified     :   SpecHDL / trilha RISC-V -- REQ: FR-RV-08, FR-RV-09, FR-RV-10
--
--                  Two generics were added so a test can swap the program without
--                  editing VHDL by hand (see specs/decisions.md, ADR-003):
--
--                    ROM_INIT_FILE   ""    -> keep using INSTRUCTION_MEMORY_CONTENT,
--                                             the constant from memory_package.vhd.
--                                             This is the default, so the original
--                                             behaviour and the synthesis path are
--                                             preserved (FR-RV-10).
--                                    path  -> read the program from a .ram image at
--                                             elaboration time (FR-RV-09).
--
--                    ROM_SIZE_WORDS  0     -> size the ROM as INSTRUCTION_MEMORY_SIZE_WORDS.
--                                    n     -> size the ROM as n 32-bit words.
--
--                  .ram image format (FR-RV-08), produced by
--                  examples/RISCV32I/tools/rv_assembler.py:
--                    * one 32-bit word per line, 8 hexadecimal digits, no 0x prefix,
--                      case-insensitive;
--                    * line index 0 is byte address 0x00000000, line n is byte address 4*n;
--                    * blank lines are ignored; '#' starts a comment that runs to the
--                      end of the line;
--                    * words not present in the file read as 0x00000000;
--                    * the program terminates on a self-loop (`j halt`, 0x0000006f).

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use STD.TEXTIO.ALL;
use work.memory_package.all;


entity instruction_memory is
    generic(
        ROM_INIT_FILE   : string  := "";     -- "" keeps INSTRUCTION_MEMORY_CONTENT
        ROM_SIZE_WORDS  : integer := 0       -- 0 keeps INSTRUCTION_MEMORY_SIZE_WORDS
    );
    port(
        addr        : in std_logic_vector(31 downto 0);

        instr       : out std_logic_vector(31 downto 0)
    );
end instruction_memory;


architecture Behavioral of instruction_memory is

    -- effective ROM depth, in 32-bit words
    function effective_rom_words return natural is
    begin
        if ROM_SIZE_WORDS > 0 then
            return ROM_SIZE_WORDS;
        else
            return INSTRUCTION_MEMORY_SIZE_WORDS;
        end if;
    end function;

    constant ROM_WORDS : natural := effective_rom_words;

    -- hexadecimal digit -> value, -1 when the character is not a hex digit
    function hex_digit(c : character) return integer is
    begin
        case c is
            when '0' to '9' => return character'pos(c) - character'pos('0');
            when 'a' to 'f' => return character'pos(c) - character'pos('a') + 10;
            when 'A' to 'F' => return character'pos(c) - character'pos('A') + 10;
            when others     => return -1;
        end case;
    end function;

    -- Builds the ROM contents at elaboration time.
    -- With ROM_INIT_FILE = "" this is a pure copy of the VHDL constant, which is
    -- what the synthesis path uses (FR-RV-10).
    impure function load_rom return INSTRUCTION_WORDS_t is
        variable m      : INSTRUCTION_WORDS_t(0 to ROM_WORDS-1) := (others => (others => '0'));
        file     f      : text;
        variable status : file_open_status;
        variable l      : line;
        variable acc    : unsigned(31 downto 0);
        variable digits : natural;
        variable hv     : integer;
        variable idx    : natural := 0;
        variable c      : character;
    begin
        if ROM_INIT_FILE = "" then
            for i in 0 to ROM_WORDS-1 loop
                if i < INSTRUCTION_MEMORY_SIZE_WORDS then
                    m(i) := INSTRUCTION_MEMORY_CONTENT(i);
                end if;
            end loop;
            return m;
        end if;

        file_open(status, f, ROM_INIT_FILE, read_mode);
        assert status = open_ok
            report "instruction_memory: nao foi possivel abrir a imagem .ram: " & ROM_INIT_FILE
            severity failure;

        while not endfile(f) loop
            readline(f, l);
            acc    := (others => '0');
            digits := 0;
            if l /= null then
                for i in l.all'range loop
                    c := l.all(i);
                    exit when c = '#';                       -- comentario ate o fim da linha
                    if c = ' ' or c = HT or c = CR then
                        exit when digits > 0;                -- fim da palavra
                    else
                        hv := hex_digit(c);
                        assert hv >= 0
                            report "instruction_memory: caractere invalido na imagem .ram ("
                                   & ROM_INIT_FILE & "): '" & c & "'"
                            severity failure;
                        assert digits < 8
                            report "instruction_memory: mais de 8 digitos hexadecimais numa linha de "
                                   & ROM_INIT_FILE
                            severity failure;
                        acc    := acc(27 downto 0) & to_unsigned(hv, 4);
                        digits := digits + 1;
                    end if;
                end loop;
            end if;

            if digits > 0 then                               -- linha vazia / comentario: ignorada
                assert idx < ROM_WORDS
                    report "instruction_memory: a imagem .ram (" & ROM_INIT_FILE
                           & ") nao cabe em ROM_SIZE_WORDS palavras"
                    severity failure;
                if idx < ROM_WORDS then
                    m(idx) := std_logic_vector(acc);
                end if;
                idx := idx + 1;
            end if;
        end loop;

        file_close(f);
        return m;
    end function;

    signal memory     : INSTRUCTION_WORDS_t(0 to ROM_WORDS-1) := load_rom;
    signal word_index : integer := 0;

begin
    word_index      <= to_integer(unsigned(addr(31 downto 2)));

    instr <=
        -- forbidding unaligned access
        (others => '1') when word_index >= ROM_WORDS or addr(1 downto 0) /= "00" else
        memory(word_index);

end Behavioral;
