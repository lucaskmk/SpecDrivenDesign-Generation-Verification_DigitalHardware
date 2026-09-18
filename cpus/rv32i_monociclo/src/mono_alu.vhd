-- Project      : SpecHDL / trilha RISC-V -- exemplo "CPU escrita do zero"
-- File         : mono_alu.vhd
-- Description  : Arithmetic-logic unit of the single-cycle RV32I core.
--                Purely combinational, one result per cycle.
--
-- REQ: FR-RV-03, FR-RV-04, FR-RV-05
--
-- Design note
-- -----------
-- This ALU is written from scratch for the single-cycle core; it deliberately
-- does NOT reuse cpus/rv32i_pipeline/src/ALU.vhd, because the whole point of this
-- example is to be an independent implementation that the same conformance
-- suite must accept. It does reuse `ALU_OP_TYPE_t` from cpu_package.vhd so the
-- already-verified mul_div_unit.vhd can be dropped in unchanged when
-- RV32M_ENABLE is true.
--
-- The RV32M values of ALU_OP_TYPE_t fall through to the `others` arm and read
-- as zero here: those operations are computed by mul_div_unit and muxed over
-- this result inside cpu_monocycle.vhd.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;


entity mono_alu is
    port(
        op1     : in  std_logic_vector(31 downto 0);
        op2     : in  std_logic_vector(31 downto 0);
        op_type : in  ALU_OP_TYPE_t;

        res     : out std_logic_vector(31 downto 0)
    );
end mono_alu;


architecture Behavioral of mono_alu is
begin

    process(op1, op2, op_type)
        variable a     : unsigned(31 downto 0);
        variable b     : unsigned(31 downto 0);
        variable shamt : natural range 0 to 31;
    begin
        a     := unsigned(op1);
        b     := unsigned(op2);
        -- RV32I shifts use only the low 5 bits of the second operand
        shamt := to_integer(unsigned(op2(4 downto 0)));

        case op_type is
            when ALU_OP_TYPE_ADD =>
                res <= std_logic_vector(a + b);

            when ALU_OP_TYPE_SUB =>
                res <= std_logic_vector(a - b);

            when ALU_OP_TYPE_SLT =>
                if signed(op1) < signed(op2) then
                    res <= x"00000001";
                else
                    res <= x"00000000";
                end if;

            when ALU_OP_TYPE_SLTU =>
                if a < b then
                    res <= x"00000001";
                else
                    res <= x"00000000";
                end if;

            when ALU_OP_TYPE_AND =>
                res <= op1 and op2;

            when ALU_OP_TYPE_OR =>
                res <= op1 or op2;

            when ALU_OP_TYPE_XOR =>
                res <= op1 xor op2;

            when ALU_OP_TYPE_SLL =>
                res <= std_logic_vector(shift_left(a, shamt));

            when ALU_OP_TYPE_SRL =>
                res <= std_logic_vector(shift_right(a, shamt));

            when ALU_OP_TYPE_SRA =>
                res <= std_logic_vector(shift_right(signed(op1), shamt));

            when others =>
                -- RV32M operations: computed by mul_div_unit, not here
                res <= (others => '0');
        end case;
    end process;

end Behavioral;
