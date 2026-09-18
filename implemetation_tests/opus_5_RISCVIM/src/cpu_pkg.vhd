-- =============================================================================
-- cpu_pkg.vhd -- shared types and constants for the rv32im_sc CPU
-- REQ: FR-01, FR-06, NFR-01
--
-- Design : rv32im_sc (RISC-V RV32IM, single-cycle)
-- Source : implemetation_tests/opus_5_RISCVIM/specs/spec.json
--
-- Every magic number of the memory map (FR-06) lives here so that address
-- decoding is never duplicated across blocks.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package cpu_pkg is

    -- REQ: FR-01 -- 32-bit word / register / address
    constant XLEN : natural := 32;

    subtype word_t is std_logic_vector(XLEN - 1 downto 0);

    -- REQ: FR-06 -- memory map
    -- Instruction ROM : 0x00000000 .. 0x00000FFF (1024 words, .text + .rodata)
    -- Data RAM        : 0x00FC8000 .. 0x00FC8FFF (1024 words, scratchpad)
    constant ROM_SIZE_WORDS : natural := 1024;
    constant RAM_SIZE_WORDS : natural := 1024;

    -- Upper 20 bits of an address that select each region. Both regions are
    -- 4 KB aligned, so the low 12 bits are always the offset inside them and
    -- can index the arrays without ever going out of bounds.
    constant ROM_TAG : std_logic_vector(19 downto 0) := x"00000";
    constant RAM_TAG : std_logic_vector(19 downto 0) := x"00FC8";

    -- REQ: FR-09 -- reset vector
    constant RESET_VECTOR : word_t := x"00000000";

    -- REQ: FR-07 -- value read back on an out-of-range or misaligned access
    constant INVALID_READ : word_t := x"FFFFFFFF";

    type rom_image_t is array (0 to ROM_SIZE_WORDS - 1) of word_t;
    type ram_array_t is array (0 to RAM_SIZE_WORDS - 1) of word_t;

    -- REQ: FR-03, FR-12 -- ALU operation codes (internal encoding)
    constant ALU_ADD    : std_logic_vector(3 downto 0) := "0000";
    constant ALU_SUB    : std_logic_vector(3 downto 0) := "0001";
    constant ALU_AND    : std_logic_vector(3 downto 0) := "0010";
    constant ALU_OR     : std_logic_vector(3 downto 0) := "0011";
    constant ALU_XOR    : std_logic_vector(3 downto 0) := "0100";
    constant ALU_SLL    : std_logic_vector(3 downto 0) := "0101";
    constant ALU_SRL    : std_logic_vector(3 downto 0) := "0110";
    constant ALU_SRA    : std_logic_vector(3 downto 0) := "0111";
    constant ALU_SLT    : std_logic_vector(3 downto 0) := "1000";
    constant ALU_SLTU   : std_logic_vector(3 downto 0) := "1001";
    constant ALU_PASS_B : std_logic_vector(3 downto 0) := "1010";  -- lui

    -- REQ: FR-04 -- M extension operation codes. Deliberately identical to
    -- the RISC-V funct3 field of the OP opcode with funct7 = 0000001, so the
    -- control unit forwards funct3 without a translation table.
    constant MD_MUL    : std_logic_vector(2 downto 0) := "000";
    constant MD_MULH   : std_logic_vector(2 downto 0) := "001";
    constant MD_MULHSU : std_logic_vector(2 downto 0) := "010";
    constant MD_MULHU  : std_logic_vector(2 downto 0) := "011";
    constant MD_DIV    : std_logic_vector(2 downto 0) := "100";
    constant MD_DIVU   : std_logic_vector(2 downto 0) := "101";
    constant MD_REM    : std_logic_vector(2 downto 0) := "110";
    constant MD_REMU   : std_logic_vector(2 downto 0) := "111";

    -- REQ: FR-03, FR-08 -- immediate formats
    constant IMM_I : std_logic_vector(2 downto 0) := "000";
    constant IMM_S : std_logic_vector(2 downto 0) := "001";
    constant IMM_B : std_logic_vector(2 downto 0) := "010";
    constant IMM_U : std_logic_vector(2 downto 0) := "011";
    constant IMM_J : std_logic_vector(2 downto 0) := "100";
    constant IMM_NONE : std_logic_vector(2 downto 0) := "111";

    -- RISC-V opcodes (instr(6 downto 0)) -- REQ: FR-03, FR-04
    constant OPC_LUI    : std_logic_vector(6 downto 0) := "0110111";
    constant OPC_AUIPC  : std_logic_vector(6 downto 0) := "0010111";
    constant OPC_JAL    : std_logic_vector(6 downto 0) := "1101111";
    constant OPC_JALR   : std_logic_vector(6 downto 0) := "1100111";
    constant OPC_BRANCH : std_logic_vector(6 downto 0) := "1100011";
    constant OPC_LOAD   : std_logic_vector(6 downto 0) := "0000011";
    constant OPC_STORE  : std_logic_vector(6 downto 0) := "0100011";
    constant OPC_OP_IMM : std_logic_vector(6 downto 0) := "0010011";
    constant OPC_OP     : std_logic_vector(6 downto 0) := "0110011";

end package cpu_pkg;
