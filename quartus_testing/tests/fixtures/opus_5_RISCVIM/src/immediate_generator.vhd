-- =============================================================================
-- immediate_generator.vhd -- immediate extraction and sign extension
-- REQ: FR-03, FR-08
--
-- Pure bit shuffling: costs wires and no adder. Concentrating it in one block
-- isolates the most error-prone part of RISC-V decoding (the B and J
-- immediates have their bits scrambled inside the instruction word).
--
-- Naming note: the intermediate signals are *not* called imm_i/imm_s/...
-- VHDL identifiers are case insensitive, so `imm_i` would be the same name as
-- the package constant IMM_I and would shadow it inside this architecture --
-- the comparison `imm_format = IMM_I` then silently compares a 3-bit vector
-- against a 32-bit signal, which std_logic_1164 answers with `false` instead
-- of an error. That bug was caught by this block's testbench (the output was
-- stuck at zero for every format), which is precisely why block-level
-- verification exists (FR-10 / constitution principle 4).
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity immediate_generator is
    port (
        instr      : in  word_t;
        imm_format : in  std_logic_vector(2 downto 0);
        imm        : out word_t
    );
end entity immediate_generator;

architecture rtl of immediate_generator is
    signal itype : word_t;
    signal stype : word_t;
    signal btype : word_t;
    signal utype : word_t;
    signal jtype : word_t;
begin

    -- REQ: FR-03 -- I-type: imm[11:0] = instr[31:20], sign extended
    itype <= (31 downto 12 => instr(31)) & instr(31 downto 20);

    -- REQ: FR-03 -- S-type: imm[11:5] = instr[31:25], imm[4:0] = instr[11:7]
    stype <= (31 downto 12 => instr(31)) & instr(31 downto 25) & instr(11 downto 7);

    -- REQ: FR-08 -- B-type: imm[12|10:5|4:1|11], always even
    btype <= (31 downto 13 => instr(31)) & instr(31) & instr(7)
             & instr(30 downto 25) & instr(11 downto 8) & '0';

    -- REQ: FR-03 -- U-type: imm[31:12] = instr[31:12], low 12 bits zero
    utype <= instr(31 downto 12) & x"000";

    -- REQ: FR-08 -- J-type: imm[20|10:1|11|19:12], always even
    jtype <= (31 downto 21 => instr(31)) & instr(31) & instr(19 downto 12)
             & instr(20) & instr(30 downto 21) & '0';

    -- Format mux as a process with an explicit sensitivity list: the format
    -- codes are package constants, which VHDL-93 does not accept as case or
    -- selected-assignment choices (globally, but not locally, static).
    process (imm_format, itype, stype, btype, utype, jtype)
    begin
        if imm_format = IMM_I then
            imm <= itype;
        elsif imm_format = IMM_S then
            imm <= stype;
        elsif imm_format = IMM_B then
            imm <= btype;
        elsif imm_format = IMM_U then
            imm <= utype;
        elsif imm_format = IMM_J then
            imm <= jtype;
        else
            imm <= (others => '0');
        end if;
    end process;

end architecture rtl;
