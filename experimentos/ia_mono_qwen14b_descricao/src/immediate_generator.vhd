-- REQ: Immediate value generation for RISC-V CPU

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;

entity immediate_generator is
    port(
        instr         : in std_logic_vector(31 downto 0);
        immediate_value : out std_logic_vector(31 downto 0)
    );
end immediate_generator;

architecture Behavioral of immediate_generator is
begin

    -- Generate the immediate value based on the instruction type
    process(instr)
        variable imm : std_logic_vector(31 downto 0) := (others => '0');
    begin
        case instr(6 downto 0) is
            when INSTR_OPCODE_LUI =>
                imm := instr(31 downto 12) & "000000000000"; -- U-type

            when INSTR_OPCODE_AUIPC =>
                imm := instr(31 downto 12) & "000000000000"; -- U-type

            when INSTR_OPCODE_JAL =>
                imm := (instr(31) & instr(19 downto 12) & instr(20) & instr(30 downto 21) & '0'); -- J-type

            when INSTR_OPCODE_JALR =>
                imm := "000000000000" & instr(31 downto 20); -- I-type

            when INSTR_OPCODE_BRANCH =>
                imm := (instr(31) & instr(7) & instr(30 downto 25) & instr(11 downto 8) & '0'); -- B-type

            when INSTR_OPCODE_LOAD | INSTR_OPCODE_STORE =>
                imm := "000000000000" & instr(31 downto 20); -- I/S-type

            when INSTR_OPCODE_REG_IMM =>
                imm := (instr(31) & instr(31 downto 20)); -- I-type

            when INSTR_OPCODE_REG_REG =>
                if RV32M_ENABLE and instr(6 downto 2) = INSTR_FUNCT7_M then
                    imm := "000000000000" & instr(31 downto 25); -- M-type
                else
                    imm := (others => '0'); -- No immediate for R-type instructions
                end if;

            when others =>
                imm := (others => '0'); -- Default case, should not happen

        end case;
        immediate_value <= imm;
    end process;

end Behavioral;
