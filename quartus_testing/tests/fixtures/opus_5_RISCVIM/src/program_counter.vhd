-- =============================================================================
-- program_counter.vhd -- program counter register
-- REQ: FR-05, FR-09
--
-- Single state element of the control flow. Synchronous, active-high reset
-- forces the reset vector (FR-09); no asynchronous reset path (NFR-03).
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use work.cpu_pkg.all;

entity program_counter is
    port (
        clk     : in  std_logic;
        rst     : in  std_logic;  -- REQ: FR-09 -- synchronous, active high
        next_pc : in  word_t;
        pc      : out word_t
    );
end entity program_counter;

architecture rtl of program_counter is
    signal pc_reg : word_t := RESET_VECTOR;
begin

    pc <= pc_reg;

    -- REQ: FR-09
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                pc_reg <= RESET_VECTOR;
            else
                pc_reg <= next_pc;
            end if;
        end if;
    end process;

end architecture rtl;
