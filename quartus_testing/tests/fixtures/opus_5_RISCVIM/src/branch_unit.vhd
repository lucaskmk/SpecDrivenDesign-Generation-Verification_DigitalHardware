-- =============================================================================
-- branch_unit.vhd -- conditional branch resolution
-- REQ: FR-03, FR-08
--
-- Dedicated comparator instead of reusing the ALU: in this datapath the ALU
-- is busy computing the branch target in the same cycle (pc + imm), and a
-- second 32-bit comparator is cheap next to serialising the two operations
-- (NFR-02). The rubric rules out a flags register, so the condition is
-- evaluated straight from the register values.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity branch_unit is
    port (
        rs1_data    : in  word_t;
        rs2_data    : in  word_t;
        funct3      : in  std_logic_vector(2 downto 0);
        is_branch   : in  std_logic;
        take_branch : out std_logic
    );
end entity branch_unit;

architecture rtl of branch_unit is
    signal condition : std_logic;
begin

    -- REQ: FR-03 -- beq/bne/blt/bge/bltu/bgeu, encoded by funct3
    process (rs1_data, rs2_data, funct3)
    begin
        case funct3 is
            when "000" =>  -- beq
                if rs1_data = rs2_data then condition <= '1'; else condition <= '0'; end if;
            when "001" =>  -- bne
                if rs1_data /= rs2_data then condition <= '1'; else condition <= '0'; end if;
            when "100" =>  -- blt (signed)
                if signed(rs1_data) < signed(rs2_data) then condition <= '1'; else condition <= '0'; end if;
            when "101" =>  -- bge (signed)
                if signed(rs1_data) >= signed(rs2_data) then condition <= '1'; else condition <= '0'; end if;
            when "110" =>  -- bltu (unsigned)
                if unsigned(rs1_data) < unsigned(rs2_data) then condition <= '1'; else condition <= '0'; end if;
            when "111" =>  -- bgeu (unsigned)
                if unsigned(rs1_data) >= unsigned(rs2_data) then condition <= '1'; else condition <= '0'; end if;
            when others =>
                condition <= '0';  -- funct3 = 010/011 are not branches (FR-14)
        end case;
    end process;

    -- REQ: FR-08
    take_branch <= condition and is_branch;

end architecture rtl;
