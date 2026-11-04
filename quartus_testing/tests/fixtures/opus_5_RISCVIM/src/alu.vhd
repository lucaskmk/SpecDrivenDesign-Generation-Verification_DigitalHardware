-- =============================================================================
-- alu.vhd -- integer ALU of the RV32I base set
-- REQ: FR-03, FR-12
--
-- Purely combinational, one operation per cycle (NFR-02). Shifts use only the
-- low 5 bits of operand b (FR-12); a one-cycle barrel shifter is what keeps
-- CPI = 1, an iterative shifter would save area but break it.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity alu is
    port (
        a      : in  word_t;
        b      : in  word_t;
        alu_op : in  std_logic_vector(3 downto 0);
        result : out word_t
    );
end entity alu;

architecture rtl of alu is
    signal shamt : natural range 0 to 31;
begin

    -- REQ: FR-12 -- only b[4:0] is used as the shift amount
    shamt <= to_integer(unsigned(b(4 downto 0)));

    -- Written as an if/elsif chain instead of a case statement because the
    -- operation codes are package constants, which VHDL-93 rejects as case
    -- choices (globally but not locally static).
    process (a, b, alu_op, shamt)
    begin
        if alu_op = ALU_ADD then
            result <= std_logic_vector(unsigned(a) + unsigned(b));
        elsif alu_op = ALU_SUB then
            result <= std_logic_vector(unsigned(a) - unsigned(b));
        elsif alu_op = ALU_AND then
            result <= a and b;
        elsif alu_op = ALU_OR then
            result <= a or b;
        elsif alu_op = ALU_XOR then
            result <= a xor b;
        elsif alu_op = ALU_SLL then
            result <= std_logic_vector(shift_left(unsigned(a), shamt));
        elsif alu_op = ALU_SRL then
            result <= std_logic_vector(shift_right(unsigned(a), shamt));
        elsif alu_op = ALU_SRA then
            result <= std_logic_vector(shift_right(signed(a), shamt));
        elsif alu_op = ALU_SLT then
            -- REQ: FR-03 -- signed set-less-than (slt / slti)
            if signed(a) < signed(b) then
                result <= x"00000001";
            else
                result <= x"00000000";
            end if;
        elsif alu_op = ALU_SLTU then
            -- REQ: FR-03 -- unsigned set-less-than (sltu / sltiu)
            if unsigned(a) < unsigned(b) then
                result <= x"00000001";
            else
                result <= x"00000000";
            end if;
        elsif alu_op = ALU_PASS_B then
            -- REQ: FR-03 -- lui: the U immediate goes straight to rd
            result <= b;
        else
            result <= (others => '0');
        end if;
    end process;

end architecture rtl;
