-- Project      : simple_RISCV_RV32I_vhdl
-- Author       : Morgan Demange <https://github.com/MorganDemange>
-- Date         : July 27, 2024
-- File         : cpu_package.vhd
-- Description  : types, enums, constants, etc.


library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

package cpu_package is
  
    -- REQ: FR-RV-12, FR-RV-13, FR-RV-17
    --
    -- The eight RV32M operations were appended to this enumeration on purpose,
    -- instead of being carried to the Execute stage by a new control signal.
    --
    -- Rationale (see specs/decisions.md, ADR-007): `alu_op_type` ALREADY travels
    -- from Decode to Execute through decode_pipeline_register. Reusing it means the
    -- RV32M extension needs NO new port on any pipeline register and NO change to
    -- hazard_control_unit.vhd -- the mul/div result simply lands on `alu_result_e`,
    -- which is where the existing MEM->EX and WB->EX forwarding paths already start.
    --
    -- ALU.vhd needs no change either: its final `(others => '0')` fallback covers
    -- the new values, and CPU.vhd muxes the mul/div result over the ALU result.
    type ALU_OP_TYPE_t is (ALU_OP_TYPE_ADD, ALU_OP_TYPE_SUB, ALU_OP_TYPE_SLT, ALU_OP_TYPE_SLTU,
                            ALU_OP_TYPE_AND, ALU_OP_TYPE_OR, ALU_OP_TYPE_XOR, ALU_OP_TYPE_SLL, ALU_OP_TYPE_SRL, ALU_OP_TYPE_SRA,
                            -- RV32M standard extension
                            ALU_OP_TYPE_MUL, ALU_OP_TYPE_MULH, ALU_OP_TYPE_MULHSU, ALU_OP_TYPE_MULHU,
                            ALU_OP_TYPE_DIV, ALU_OP_TYPE_DIVU, ALU_OP_TYPE_REM, ALU_OP_TYPE_REMU);

    subtype ALU_OP_TYPE_M_t is ALU_OP_TYPE_t range ALU_OP_TYPE_MUL to ALU_OP_TYPE_REMU;

    -- '1' when the operation must be handled by mul_div_unit instead of the ALU
    function is_rv32m_op(op : ALU_OP_TYPE_t) return boolean;
                            
    type ALU_OP_SRC_t is (ALU_OP_SRC_IMM, ALU_OP_SRC_ALU_RES, ALU_OP_SRC_REG, ALU_OP_SRC_PC_IMM, ALU_OP_SRC_PC_4, ALU_OP_SRC_RD_DATA);
                            
    type BRANCH_TYPE_t is (BRANCH_TYPE_NONE, BRANCH_TYPE_BEQ, BRANCH_TYPE_BNE, BRANCH_TYPE_BLT, BRANCH_TYPE_BGE);
    
    type RD_DATA_SOURCE_t is (RD_DATA_SOURCE_PC_IMM, RD_DATA_SOURCE_PC_4, RD_DATA_SOURCE_IMM, RD_DATA_SOURCE_ALU_RESULT, RD_DATA_SOURCE_MEM_DATA_OUT);
    
    type MEM_ACCESS_WIDTH_t is (MEM_ACCESS_WIDTH_8, MEM_ACCESS_WIDTH_16, MEM_ACCESS_WIDTH_32);
    
    type PC_NEXT_SRC_t is (PC_NEXT_SRC_PC_ALU_RES, PC_NEXT_SRC_PC_IMM, PC_NEXT_SRC_PC_4);
 
 
    
    constant INSTR_NOP              : std_logic_vector(31 downto 0) := x"00000013"; -- ADDI x0, x0, 0           
                            
    -- instruction opcodes
    constant INSTR_OPCODE_LUI       : std_logic_vector(6 downto 0) := "0110111"; -- LUI
    constant INSTR_OPCODE_AUIPC     : std_logic_vector(6 downto 0) := "0010111"; -- AUIPC
    constant INSTR_OPCODE_JAL       : std_logic_vector(6 downto 0) := "1101111"; -- JAL
    constant INSTR_OPCODE_JALR      : std_logic_vector(6 downto 0) := "1100111"; -- JALR
    constant INSTR_OPCODE_BRANCH    : std_logic_vector(6 downto 0) := "1100011"; -- BEQ, BNE, BLT[U], BGE[U]
    constant INSTR_OPCODE_LOAD      : std_logic_vector(6 downto 0) := "0000011"; -- LB[U], LH[U], LW
    constant INSTR_OPCODE_STORE     : std_logic_vector(6 downto 0) := "0100011"; -- SB, SH, SW
    constant INSTR_OPCODE_REG_IMM   : std_logic_vector(6 downto 0) := "0010011"; -- ADDI, SLTI[U], XORI, ORI, ANDI, SLLI, SRLI, SRAI
    constant INSTR_OPCODE_REG_REG   : std_logic_vector(6 downto 0) := "0110011"; -- ADD, SUB, SLT[U], XOR, OR, AND, SLL, SRL, SRA  
    constant INSTR_OPCODE_FENCE     : std_logic_vector(6 downto 0) := "0001111"; -- FENCE
    constant INSTR_OPCODE_SYSTEM    : std_logic_vector(6 downto 0) := "1110011"; -- ECALL, EBREAK
    
    -- funct3
    constant INSTR_FUNCT3_JALR      : std_logic_vector(2 downto 0) := "000";   
    constant INSTR_FUNCT3_BEQ       : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_BNE       : std_logic_vector(2 downto 0) := "001";
    constant INSTR_FUNCT3_BLT       : std_logic_vector(2 downto 0) := "100";
    constant INSTR_FUNCT3_BGE       : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_BLTU      : std_logic_vector(2 downto 0) := "110";
    constant INSTR_FUNCT3_BGEU      : std_logic_vector(2 downto 0) := "111";
    constant INSTR_FUNCT3_LB        : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_LH        : std_logic_vector(2 downto 0) := "001";
    constant INSTR_FUNCT3_LW        : std_logic_vector(2 downto 0) := "010";
    constant INSTR_FUNCT3_LBU       : std_logic_vector(2 downto 0) := "100";
    constant INSTR_FUNCT3_LHU       : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_SB        : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_SH        : std_logic_vector(2 downto 0) := "001";
    constant INSTR_FUNCT3_SW        : std_logic_vector(2 downto 0) := "010";
    constant INSTR_FUNCT3_ADDI      : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_SLTI      : std_logic_vector(2 downto 0) := "010";
    constant INSTR_FUNCT3_SLTIU     : std_logic_vector(2 downto 0) := "011";
    constant INSTR_FUNCT3_XORI      : std_logic_vector(2 downto 0) := "100";
    constant INSTR_FUNCT3_ORI       : std_logic_vector(2 downto 0) := "110";
    constant INSTR_FUNCT3_ANDI      : std_logic_vector(2 downto 0) := "111";
    constant INSTR_FUNCT3_SLLI      : std_logic_vector(2 downto 0) := "001";
    constant INSTR_FUNCT3_SRLI      : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_SRAI      : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_ADD       : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_SUB       : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_SLL       : std_logic_vector(2 downto 0) := "001";
    constant INSTR_FUNCT3_SLT       : std_logic_vector(2 downto 0) := "010";
    constant INSTR_FUNCT3_SLTU      : std_logic_vector(2 downto 0) := "011";
    constant INSTR_FUNCT3_XOR       : std_logic_vector(2 downto 0) := "100";
    constant INSTR_FUNCT3_SRL       : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_SRA       : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_OR        : std_logic_vector(2 downto 0) := "110";
    constant INSTR_FUNCT3_AND       : std_logic_vector(2 downto 0) := "111";
    constant INSTR_FUNCT3_FENCE     : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_ECALL     : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_EBREAK    : std_logic_vector(2 downto 0) := "000";
    
    -- funct7
    constant INSTR_FUNCT7_SLLI      : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_SRLI      : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_SRAI      : std_logic_vector(6 downto 0) := "0100000";
    constant INSTR_FUNCT7_ADD       : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_SUB       : std_logic_vector(6 downto 0) := "0100000";
    constant INSTR_FUNCT7_SLL       : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_SLT       : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_SLTU      : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_XOR       : std_logic_vector(6 downto 0) := "0000000";   
    constant INSTR_FUNCT7_SRL       : std_logic_vector(6 downto 0) := "0000000";
    constant INSTR_FUNCT7_SRA       : std_logic_vector(6 downto 0) := "0100000";
    constant INSTR_FUNCT7_OR        : std_logic_vector(6 downto 0) := "0000000";    
    constant INSTR_FUNCT7_AND       : std_logic_vector(6 downto 0) := "0000000";   

    -- RV32M standard extension: every M instruction is an R-type on the REG_REG
    -- opcode with funct7 = 0000001, selected by funct3 (FR-RV-13).
    constant INSTR_FUNCT7_M         : std_logic_vector(6 downto 0) := "0000001";
    constant INSTR_FUNCT3_MUL       : std_logic_vector(2 downto 0) := "000";
    constant INSTR_FUNCT3_MULH      : std_logic_vector(2 downto 0) := "001";
    constant INSTR_FUNCT3_MULHSU    : std_logic_vector(2 downto 0) := "010";
    constant INSTR_FUNCT3_MULHU     : std_logic_vector(2 downto 0) := "011";
    constant INSTR_FUNCT3_DIV       : std_logic_vector(2 downto 0) := "100";
    constant INSTR_FUNCT3_DIVU      : std_logic_vector(2 downto 0) := "101";
    constant INSTR_FUNCT3_REM       : std_logic_vector(2 downto 0) := "110";
    constant INSTR_FUNCT3_REMU      : std_logic_vector(2 downto 0) := "111";

end package cpu_package;


package body cpu_package is

    function is_rv32m_op(op : ALU_OP_TYPE_t) return boolean is
    begin
        return op >= ALU_OP_TYPE_MUL;
    end function;

end package body cpu_package;
