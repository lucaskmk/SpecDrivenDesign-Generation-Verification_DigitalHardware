-- Project      : simple_RISCV_RV32I_vhdl  (SpecHDL / trilha RISC-V)
-- File         : mul_div_unit.vhd
-- Description  : RV32M standard extension: MUL, MULH, MULHSU, MULHU,
--                DIV, DIVU, REM, REMU.
--
-- REQ: FR-RV-12, FR-RV-13, FR-RV-14, FR-RV-17
--
-- Design note (see specs/decisions.md, ADR-007)
-- ---------------------------------------------
-- This unit is PURELY COMBINATIONAL: it has the same 1-cycle latency as the ALU
-- it sits beside in the Execute stage. That is a deliberate choice, and it is
-- what makes the extension cheap in verification terms:
--
--   * no new stall source, so hazard_control_unit.vhd is untouched;
--   * no new port on any pipeline register, so the 5-stage pipeline is untouched;
--   * the result lands on `alu_result_e`, so the existing MEM->EX and WB->EX
--     forwarding paths carry mul/div results for free.
--
-- The price is paid in AREA and in CRITICAL PATH, not in cycles -- the divider
-- below is a 32-deep chain of compare/subtract stages. That trade-off is the
-- point of the RV32I vs RV32IM comparison and is measured by real synthesis
-- (ghdl synth + yosys stat), never estimated.
--
-- An iterative multi-cycle variant is registered as future work; it would need a
-- `stall` input added to decode_pipeline_register so the Execute stage could be
-- held while the unit iterates.
--
-- Semantics (RISC-V Unprivileged ISA, chapter "M")
-- ------------------------------------------------
-- All results are 32 bits, two's complement, modulo 2^32. RISC-V does NOT trap
-- on division by zero nor on signed division overflow; both produce defined
-- values, implemented here and cross-checked in Python by
-- rvverify/reference.py:
--
--   DIV   rs2 = 0            -> -1  (0xFFFFFFFF)
--   DIV   -2^31 / -1         -> -2^31          (overflow wraps, no trap)
--   DIVU  rs2 = 0            -> 2^32-1
--   REM   rs2 = 0            -> rs1
--   REM   -2^31 % -1         -> 0
--   REMU  rs2 = 0            -> rs1
--
-- REM takes the sign of the dividend; DIV truncates toward zero.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;


entity mul_div_unit is
    port(
        op1         : in std_logic_vector(31 downto 0);     -- rs1
        op2         : in std_logic_vector(31 downto 0);     -- rs2
        op_type     : in ALU_OP_TYPE_t;

        -- Observability only, for the cocotb efficiency metrics (FR-RV-24).
        -- `start` is driven high by CPU.vhd when a real (non-bubble) RV32M
        -- instruction is in the Execute stage.
        start       : in std_logic;

        res         : out std_logic_vector(31 downto 0);
        -- Always '0': this unit completes in the same cycle it is issued.
        -- Kept as a port so that an iterative variant can replace this one
        -- without changing the CPU interface.
        busy        : out std_logic
    );
end mul_div_unit;


architecture Behavioral of mul_div_unit is

    -- ---- multiplication -------------------------------------------------
    -- 32x32 products, wide enough that no bit of the result is lost:
    --   signed   x signed   -> 64 bits
    --   unsigned x unsigned -> 64 bits
    --   signed   x unsigned -> 65 bits (rs2 zero-extended to a 33-bit signed)
    signal prod_ss  : signed(63 downto 0);
    signal prod_uu  : unsigned(63 downto 0);
    signal prod_su  : signed(64 downto 0);

    -- ---- division -------------------------------------------------------
    signal is_signed_div : boolean;
    signal mag1, mag2    : unsigned(31 downto 0);   -- |op1|, |op2|
    signal div_n, div_d  : unsigned(31 downto 0);   -- dividend, divisor fed to the divider
    signal quo_u, rem_u  : unsigned(31 downto 0);   -- unsigned quotient and remainder

    signal div_by_zero   : boolean;
    signal sign_op1      : std_logic;
    signal quo_negative  : boolean;                 -- signed quotient must be negated

    signal div_res, rem_res : std_logic_vector(31 downto 0);

begin

    busy <= '0';                        -- combinational unit: never busy

    -- keep `start` formally read so the port cannot be optimised away before
    -- the VPI can observe it
    -- (no functional effect: the unit is stateless)

    ------------------------------------------------------------------------
    -- Multiplication
    ------------------------------------------------------------------------
    prod_ss <= signed(op1) * signed(op2);
    prod_uu <= unsigned(op1) * unsigned(op2);
    prod_su <= signed(op1) * signed('0' & op2);

    ------------------------------------------------------------------------
    -- Division: one restoring divider shared by DIV/DIVU/REM/REMU.
    --
    -- Signed operands are reduced to magnitudes first, so a single unsigned
    -- divider serves all four instructions. The signed overflow case
    -- (-2^31 / -1) needs no special handling here: |-2^31| = 2^31 fits an
    -- unsigned(31 downto 0), the quotient comes out as 0x80000000, and read
    -- back as signed that is exactly the -2^31 the ISA requires.
    ------------------------------------------------------------------------
    is_signed_div <= (op_type = ALU_OP_TYPE_DIV) or (op_type = ALU_OP_TYPE_REM);

    mag1 <= unsigned(-signed(op1)) when op1(31) = '1' else unsigned(op1);
    mag2 <= unsigned(-signed(op2)) when op2(31) = '1' else unsigned(op2);

    div_n <= mag1 when is_signed_div else unsigned(op1);
    div_d <= mag2 when is_signed_div else unsigned(op2);

    -- restoring division, most significant bit first
    divider : process(div_n, div_d)
        variable r : unsigned(32 downto 0);
        variable q : unsigned(31 downto 0);
        variable d : unsigned(32 downto 0);
    begin
        r := (others => '0');
        q := (others => '0');
        d := '0' & div_d;
        for i in 31 downto 0 loop
            r := r(31 downto 0) & div_n(i);
            if r >= d then
                r := r - d;
                q(i) := '1';
            end if;
        end loop;
        quo_u <= q;
        rem_u <= r(31 downto 0);
    end process;

    div_by_zero  <= (unsigned(op2) = 0);
    sign_op1     <= op1(31);
    -- signed quotient is negative when the operand signs differ
    quo_negative <= (op1(31) /= op2(31));

    -- DIV / DIVU result
    div_res <=
        (others => '1')                                     when div_by_zero else                 -- -1 and 2^32-1 share this encoding
        std_logic_vector(-signed(quo_u))                    when is_signed_div and quo_negative else
        std_logic_vector(quo_u);

    -- REM / REMU result: remainder takes the sign of the dividend
    rem_res <=
        op1                                                 when div_by_zero else
        std_logic_vector(-signed(rem_u))                    when is_signed_div and sign_op1 = '1' else
        std_logic_vector(rem_u);

    ------------------------------------------------------------------------
    -- Result selection
    ------------------------------------------------------------------------
    with op_type select
        res <=
            std_logic_vector(prod_uu(31 downto 0))          when ALU_OP_TYPE_MUL,      -- low 32 bits: sign-agnostic
            std_logic_vector(prod_ss(63 downto 32))         when ALU_OP_TYPE_MULH,
            std_logic_vector(prod_su(63 downto 32))         when ALU_OP_TYPE_MULHSU,
            std_logic_vector(prod_uu(63 downto 32))         when ALU_OP_TYPE_MULHU,
            div_res                                         when ALU_OP_TYPE_DIV,
            div_res                                         when ALU_OP_TYPE_DIVU,
            rem_res                                         when ALU_OP_TYPE_REM,
            rem_res                                         when ALU_OP_TYPE_REMU,
            (others => '0')                                 when others;

end Behavioral;
