-- src/decoder.vhd
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
        branch_type   : out BRANCH_TYPE_t;
        rd_data_source : out RD_DATA_SOURCE_t
    );
end decoder;

architecture Behavioral of decoder is
    signal opcode, funct3, funct7 : std_logic_vector(6 downto 0);
    signal rs1, rs2, rd : std_logic_vector(4 downto 0);
    signal imm_i, imm_s, imm_b, imm_u, imm_j : std_logic_vector(31 downto 0);
begin
    -- Extract fields from the instruction
    opcode <= instr(6 downto 0);
    funct3 <= instr(14 downto 12);
    funct7 <= instr(31 downto 25);
    rs1 <= instr(19 downto 15);
    rs2 <= instr(24 downto 20);
    rd <= instr(11 downto 7);

    -- Immediate fields
    imm_i <= std_logic_vector(resize(signed(instr(31 downto 20)), 32));
    imm_s <= std_logic_vector(resize(signed(instr(31 downto 25) & instr(11 downto 7)), 32));
    imm_b <= std_logic_vector(resize(signed(instr(31) & instr(7) & instr(30 downto 25) & instr(11 downto 8) & "0"), 32));
    imm_u <= std_logic_vector(resize(unsigned(instr(31 downto 12) & "000000000000"), 32));
    imm_j <= std_logic_vector(resize(signed(instr(31) & instr(19 downto 12) & instr(20) & instr(30 downto 21) & "0"), 32));

    -- Decode logic
    process(opcode, funct3, funct7, rs1, rs2, rd, imm_i, imm_s, imm_b, imm_u, imm_j)
    begin
        alu_op_type <= ALU_OP_TYPE_ADD; -- Default value
        reg_write_enable <= '0';
        write_register <= (others => '0');
        read_register1 <= rs1;
        read_register2 <= rs2;
        mem_access_width <= MEM_ACCESS_WIDTH_8; -- Default value
        mem_write_enable <= '0';
        pc_next_src <= PC_NEXT_SRC_PC_4;
        branch_type <= BRANCH_TYPE_NONE;
        rd_data_source <= RD_DATA_SOURCE_ALU_RESULT;

        case opcode is
            when INSTR_OPCODE_LUI =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= (others => '0');
                read_register2 <= (others => '0');
                data_out1 <= imm_u;

            when INSTR_OPCODE_AUIPC =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= (others => '0');
                read_register2 <= (others => '0');
                data_out1 <= std_logic_vector(resize(unsigned(pc) + unsigned(imm_u), 32));

            when INSTR_OPCODE_JAL =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= (others => '0');
                read_register2 <= (others => '0');
                data_out1 <= std_logic_vector(resize(unsigned(pc) + unsigned(imm_j), 32));
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_JALR =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= rs1;
                read_register2 <= (others => '0');
                data_out1 <= std_logic_vector(resize(unsigned(pc) + unsigned(imm_i), 32));
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_BRANCH =>
                case funct3 is
                    when INSTR_FUNCT3_BEQ =>
                        branch_type <= BRANCH_TYPE_BEQ;
                    when INSTR_FUNCT3_BNE =>
                        branch_type <= BRANCH_TYPE_BNE;
                    when INSTR_FUNCT3_BLT =>
                        branch_type <= BRANCH_TYPE_BLT;
                    when INSTR_FUNCT3_BGE =>
                        branch_type <= BRANCH_TYPE_BGE;
                    when INSTR_FUNCT3_BLTU =>
                        branch_type <= BRANCH_TYPE_BLTU;
                    when INSTR_FUNCT3_BGEU =>
                        branch_type <= BRANCH_TYPE_BGEU;
                    when others => null;
                end case;
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_LOAD =>
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= rs1;
                read_register2 <= (others => '0');
                data_out1 <= imm_i;
                case funct3 is
                    when INSTR_FUNCT3_LB =>
                        mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_LH =>
                        mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when INSTR_FUNCT3_LW =>
                        mem_access_width <= MEM_ACCESS_WIDTH_32;
                    when INSTR_FUNCT3_LBU =>
                        mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_LHU =>
                        mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when others => null;
                end case;

            when INSTR_OPCODE_STORE =>
                read_register1 <= rs1;
                read_register2 <= rs2;
                data_out1 <= imm_s;
                case funct3 is
                    when INSTR_FUNCT3_SB =>
                        mem_access_width <= MEM_ACCESS_WIDTH_8;
                        mem_write_enable <= '1';
                    when INSTR_FUNCT3_SH =>
                        mem_access_width <= MEM_ACCESS_WIDTH_16;
                        mem_write_enable <= '1';
                    when INSTR_FUNCT3_SW =>
                        mem_access_width <= MEM_ACCESS_WIDTH_32;
                        mem_write_enable <= '1';
                    when others => null;
                end case;

            when INSTR_OPCODE_REG_IMM =>
                reg_write_enable <= '1';
                write_register <= rd;
                read_register1 <= rs1;
                read_register2 <= (others => '0');
                data_out1 <= imm_i;
                case funct3 is
                    when INSTR_FUNCT3_ADDI =>
                        alu_op_type <= ALU_OP_TYPE_ADD;
                    when INSTR_FUNCT3_SLTI =>
                        alu_op_type <= ALU_OP_TYPE_SLT;
                    when INSTR_FUNCT3_SLTIU =>
                        alu_op_type <= ALU_OP_TYPE_SLTU;
                    when INSTR_FUNCT3_XORI =>
                        alu_op_type <= ALU_OP_TYPE_XOR;
                    when INSTR_FUNCT3_ORI =>
                        alu_op_type <= ALU_OP_TYPE_OR;
                    when INSTR_FUNCT3_ANDI =>
                        alu_op_type <= ALU_OP_TYPE_AND;
                    when INSTR_FUNCT3_SLLI =>
                        alu_op_type <= ALU_OP_TYPE_SLL;
                    when INSTR_FUNCT3_SRLI | INSTR_FUNCT3_SRAI =>
                        if funct7 = INSTR_FUNCT7_SRLI then
                            alu_op_type <= ALU_OP_TYPE_SRL;
                        else
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
                        else
                            alu_op_type <= ALU_OP_TYPE_SUB;
                        end if;
                    when INSTR_FUNCT3_SLT =>
                        alu_op_type <= ALU_OP_TYPE_SLT;
                    when INSTR_FUNCT3_SLTU =>
                        alu_op_type <= ALU_OP_TYPE_SLTU;
                    when INSTR_FUNCT3_XOR =>
                        alu_op_type <= ALU_OP_TYPE_XOR;
                    when INSTR_FUNCT3_OR =>
                        alu_op_type <= ALU_OP_TYPE_OR;
                    when INSTR_FUNCT3_AND =>
                        alu_op_type <= ALU_OP_TYPE_AND;
                    when INSTR_FUNCT3_SLL =>
                        alu_op_type <= ALU_OP_TYPE_SLL;
                    when INSTR_FUNCT3_SRL | INSTR_FUNCT3_SRA =>
                        if funct7 = INSTR_FUNCT7_SRL then
                            alu_op_type <= ALU_OP_TYPE_SRL;
                        else
                            alu_op_type <= ALU_OP_TYPE_SRA;
                        end if;
                    when others => null;
                end case;

            when INSTR_OPCODE_FENCE =>
                -- Not required, do nothing

            when INSTR_OPCODE_SYSTEM =>
                -- Not required, do nothing

            when others =>
                -- Invalid instruction, do nothing
        end case;
    end process;
end Behavioral;
