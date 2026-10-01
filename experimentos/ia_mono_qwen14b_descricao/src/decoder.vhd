-- REQ: FR-RV-04 (RV32I semantics), FR-RV-16 (RV32M_ENABLE)

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;

entity decoder is
    port(
        instr         : in std_logic_vector(31 downto 0);
        alu_op_type   : out ALU_OP_TYPE_t;
        reg_write_enable : out std_logic;
        write_register : out std_logic_vector(4 downto 0);
        read_register1 : out std_logic_vector(4 downto 0);
        read_register2 : out std_logic_vector(4 downto 0);
        mem_access_width : out MEM_ACCESS_WIDTH_t;
        mem_write_enable : out std_logic;
        pc_next_src   : out PC_NEXT_SRC_t;
        branch_type   : out BRANCH_TYPE_t
    );
end decoder;

architecture Behavioral of decoder is
    signal opcode       : std_logic_vector(6 downto 0);
    signal funct3       : std_logic_vector(2 downto 0);
    signal funct7       : std_logic_vector(6 downto 0);
    signal rd           : std_logic_vector(4 downto 0);
    signal rs1          : std_logic_vector(4 downto 0);
    signal rs2          : std_logic_vector(4 downto 0);
begin
    -- Extract fields from the instruction
    opcode <= instr(6 downto 0);
    funct3 <= instr(14 downto 12);
    funct7 <= instr(31 downto 25);
    rd   <= instr(11 downto 7);
    rs1  <= instr(19 downto 15);
    rs2  <= instr(24 downto 20);

    -- Default assignments
    alu_op_type <= ALU_OP_TYPE_ADD;
    reg_write_enable <= '0';
    write_register <= (others => '0');
    read_register1 <= rs1;
    read_register2 <= rs2;
    mem_access_width <= MEM_ACCESS_WIDTH_32;
    mem_write_enable <= '0';
    pc_next_src <= PC_NEXT_SRC_PC_4;
    branch_type <= BRANCH_TYPE_NONE;

    -- Decode the instruction
    process(opcode, funct3, funct7, rd, rs1, rs2)
    begin
        case opcode is
            when INSTR_OPCODE_LUI =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= (others => '0');
                pc_next_src <= PC_NEXT_SRC_PC_4;

            when INSTR_OPCODE_AUIPC =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= std_logic_vector(to_unsigned(RESET_HANDLER_ADDRESS, 32));
                pc_next_src <= PC_NEXT_SRC_PC_4;

            when INSTR_OPCODE_JAL =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= std_logic_vector(unsigned(pc_next_src) + 4);
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_JALR =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= std_logic_vector(unsigned(pc_next_src) + 4);
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_BRANCH =>
                case funct3 is
                    when INSTR_FUNCT3_BEQ => branch_type <= BRANCH_TYPE_BEQ;
                    when INSTR_FUNCT3_BNE => branch_type <= BRANCH_TYPE_BNE;
                    when INSTR_FUNCT3_BLT => branch_type <= BRANCH_TYPE_BLT;
                    when INSTR_FUNCT3_BGE => branch_type <= BRANCH_TYPE_BGE;
                    when INSTR_FUNCT3_BLTU => branch_type <= BRANCH_TYPE_NONE; -- Not supported
                    when INSTR_FUNCT3_BGEU => branch_type <= BRANCH_TYPE_NONE; -- Not supported
                    when others => null;
                end case;
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_LOAD =>
                reg_write_enable <= '1';
                write_register <= rd;
                read_register2 <= rs2;
                case funct3 is
                    when INSTR_FUNCT3_LB => mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_LH => mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when INSTR_FUNCT3_LW => mem_access_width <= MEM_ACCESS_WIDTH_32;
                    when INSTR_FUNCT3_LBU => mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_LHU => mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when others => null;
                end case;

            when INSTR_OPCODE_STORE =>
                mem_write_enable <= '1';
                read_register2 <= rs2;
                case funct3 is
                    when INSTR_FUNCT3_SB => mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_SH => mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when INSTR_FUNCT3_SW => mem_access_width <= MEM_ACCESS_WIDTH_32;
                    when others => null;
                end case;

            when INSTR_OPCODE_REG_IMM =>
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= rs1;
                case funct3 is
                    when INSTR_FUNCT3_ADDI => alu_op_type <= ALU_OP_TYPE_ADD;
                    when INSTR_FUNCT3_SLTI => alu_op_type <= ALU_OP_TYPE_SLT;
                    when INSTR_FUNCT3_SLTIU => alu_op_type <= ALU_OP_TYPE_SLTU;
                    when INSTR_FUNCT3_XORI => alu_op_type <= ALU_OP_TYPE_XOR;
                    when INSTR_FUNCT3_ORI => alu_op_type <= ALU_OP_TYPE_OR;
                    when INSTR_FUNCT3_ANDI => alu_op_type <= ALU_OP_TYPE_AND;
                    when INSTR_FUNCT3_SLLI => alu_op_type <= ALU_OP_TYPE_SLL;
                    when INSTR_FUNCT3_SRLI | INSTR_FUNCT3_SRAI =>
                        if funct7 = INSTR_FUNCT7_SRLI then
                            alu_op_type <= ALU_OP_TYPE_SRL;
                        elsif funct7 = INSTR_FUNCT7_SRAI then
                            alu_op_type <= ALU_OP_TYPE_SRA;
                        end if;
                    when others => null;
                end case;

            when INSTR_OPCODE_REG_REG =>
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= rs1;
                read_register2 <= rs2;
                case funct3 is
                    when INSTR_FUNCT3_ADD | INSTR_FUNCT3_SUB =>
                        if funct7 = INSTR_FUNCT7_ADD then
                            alu_op_type <= ALU_OP_TYPE_ADD;
                        elsif funct7 = INSTR_FUNCT7_SUB then
                            alu_op_type <= ALU_OP_TYPE_SUB;
                        end if;
                    when INSTR_FUNCT3_SLL => alu_op_type <= ALU_OP_TYPE_SLL;
                    when INSTR_FUNCT3_SLT => alu_op_type <= ALU_OP_TYPE_SLT;
                    when INSTR_FUNCT3_SLTU => alu_op_type <= ALU_OP_TYPE_SLTU;
                    when INSTR_FUNCT3_XOR => alu_op_type <= ALU_OP_TYPE_XOR;
                    when INSTR_FUNCT3_SRL | INSTR_FUNCT3_SRA =>
                        if funct7 = INSTR_FUNCT7_SRL then
                            alu_op_type <= ALU_OP_TYPE_SRL;
                        elsif funct7 = INSTR_FUNCT7_SRA then
                            alu_op_type <= ALU_OP_TYPE_SRA;
                        end if;
                    when INSTR_FUNCT3_OR => alu_op_type <= ALU_OP_TYPE_OR;
                    when INSTR_FUNCT3_AND => alu_op_type <= ALU_OP_TYPE_AND;
                    when others => null;
                end case;

            when INSTR_OPCODE_FENCE =>
                -- Not supported
                null;

            when INSTR_OPCODE_SYSTEM =>
                -- Not supported
                null;

            when others =>
                -- Invalid instruction, do nothing
                null;
        end case;
    end process;
end Behavioral;
