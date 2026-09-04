-- =============================================================================
-- mul_div_unit.vhd -- standard M extension (multiply / divide)
-- REQ: FR-04, FR-11
--
-- Separate from the ALU because only this unit needs the 64-bit product path;
-- keeping it out of the ALU avoids widening the datapath of every integer
-- instruction (NFR-02).
--
-- Combinational so that CPI stays 1 (NFR-02), at the cost of the worst
-- critical path in the design -- trade-off recorded in architecture.json
-- ("implementacao de div/rem"). A restoring sequential divider would be
-- smaller but would need stall logic, which the rubric rules out.
--
-- Edge semantics of the RISC-V spec (FR-11):
--   divisor = 0        -> div = -1, divu = 0xFFFFFFFF, rem = a, remu = a
--   -2^31 / -1         -> div = -2^31, rem = 0
-- Both cases are handled before the division operators are evaluated, so the
-- overflow value is never produced by the arithmetic itself.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity mul_div_unit is
    port (
        a      : in  word_t;
        b      : in  word_t;
        md_op  : in  std_logic_vector(2 downto 0);
        result : out word_t
    );
end entity mul_div_unit;

architecture rtl of mul_div_unit is
    constant INT_MIN : word_t := x"80000000";
    constant MINUS_1 : word_t := x"FFFFFFFF";

    -- REQ: FR-04 -- 64-bit products
    signal prod_ss : signed(63 downto 0);    -- signed   x signed
    signal prod_uu : unsigned(63 downto 0);  -- unsigned x unsigned
    signal prod_su : signed(65 downto 0);    -- signed   x unsigned (33x33)
begin

    prod_ss <= signed(a) * signed(b);
    prod_uu <= unsigned(a) * unsigned(b);
    prod_su <= resize(signed(a), 33) * signed('0' & b);

    -- if/elsif chain instead of a case statement: the operation codes are
    -- package constants, which VHDL-93 rejects as case choices.
    process (a, b, md_op, prod_ss, prod_uu, prod_su)
        variable div_by_zero : boolean;
        variable overflow    : boolean;
    begin
        div_by_zero := (b = x"00000000");
        overflow    := (a = INT_MIN) and (b = MINUS_1);

        -- REQ: FR-04 -- multiplications
        if md_op = MD_MUL then
            result <= std_logic_vector(prod_uu(31 downto 0));
        elsif md_op = MD_MULH then
            result <= std_logic_vector(prod_ss(63 downto 32));
        elsif md_op = MD_MULHSU then
            result <= std_logic_vector(prod_su(63 downto 32));
        elsif md_op = MD_MULHU then
            result <= std_logic_vector(prod_uu(63 downto 32));

        -- REQ: FR-04, FR-11 -- signed division, truncated toward zero
        elsif md_op = MD_DIV then
            if div_by_zero then
                result <= MINUS_1;
            elsif overflow then
                result <= INT_MIN;
            else
                result <= std_logic_vector(signed(a) / signed(b));
            end if;

        -- REQ: FR-04, FR-11 -- unsigned division
        elsif md_op = MD_DIVU then
            if div_by_zero then
                result <= MINUS_1;
            else
                result <= std_logic_vector(unsigned(a) / unsigned(b));
            end if;

        -- REQ: FR-04, FR-11 -- signed remainder, sign of the dividend
        elsif md_op = MD_REM then
            if div_by_zero then
                result <= a;
            elsif overflow then
                result <= (others => '0');
            else
                result <= std_logic_vector(signed(a) rem signed(b));
            end if;

        -- REQ: FR-04, FR-11 -- unsigned remainder
        elsif md_op = MD_REMU then
            if div_by_zero then
                result <= a;
            else
                result <= std_logic_vector(unsigned(a) rem unsigned(b));
            end if;

        else
            result <= (others => '0');
        end if;
    end process;

end architecture rtl;
