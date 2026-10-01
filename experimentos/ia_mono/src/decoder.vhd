-- src/decoder.vhd
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;

entity decoder is
    port(
        instr             : in std_logic_vector(31 downto 0);
        alu_op_type       : out ALU_OP_TYPE_t;
        rd_addr1          : out std_logic_vector(4 downto 0);
        rd_addr2          : out std_logic_vector(4 downto 0);
        wr_addr           : out std_logic_vector(4 downto 0);
        wr_en             : out std_logic;
        pc_next_src       : out PC_NEXT_SRC_t;
        branch_type       : out BRANCH_TYPE_t;
        mem_access_width  : out MEM_ACCESS_WIDTH_t;
        mem_write_enable  : out std_logic;
        rd_data_source    : out RD_DATA_SOURCE_t
    );
end decoder;

architecture Behavioral of decoder is
    signal opcode          : std_logic_vector(6 downto 0);
    signal funct3          : std_logic_vector(2 downto 0);
    signal funct7          : std_logic_vector(6 downto 0);
    signal rs1             : std_logic_vector(4 downto 0);
    signal rs2             : std_logic_vector(4 downto 0);
    signal rd              : std_logic_vector(4 downto 0);
    signal imm_i           : std_logic_vector(31 downto 0);
    signal imm_s           : std_logic_vector(31 downto 0);
    signal imm_b           : std_logic_vector(31 downto 0);
    signal imm_u           : std_logic_vector(31 downto 0);
    signal imm_j           : std_logic_vector(31 downto 0);

begin
    -- Extract fields from the instruction
    opcode <= instr(6 downto 0);
    funct3 <= instr(14 downto 12);
    funct7 <= instr(31 downto 25);
    rs1    <= instr(19 downto 15);
    rs2    <= instr(24 downto 20);
    rd     <= instr(11 downto 7);

    -- Immediate field decoding
    imm_i <= std_logic_vector(resize(signed(instr(31 downto 20)), 32));
    imm_s <= std_logic_vector(resize(signed(instr(31 downto 25) & instr(11 downto 7)), 32));
    imm_b <= std_logic_vector(resize(signed(instr(31) & instr(7) & instr(30 downto 25) & instr(11 downto 8) & "0"), 32));
    imm_u <= std_logic_vector(resize(unsigned(instr(31 downto 12) & "000000000000"), 32));
    imm_j <= std_logic_vector(resize(signed(instr(31) & instr(19 downto 12) & instr(20) & instr(30 downto 21) & "0"), 32));

    -- Decode logic
    process(opcode, funct3, funct7, rs1, rs2, rd, imm_i, imm_s, imm_b, imm_u, imm_j)
    begin
        alu_op_type <= ALU_OP_TYPE_ADD;  -- Default value
        rd_addr1 <= (others => '0');
        rd_addr2 <= (others => '0');
        wr_addr <= (others => '0');
        wr_en <= '0';
        pc_next_src <= PC_NEXT_SRC_PC_4;
        branch_type <= BRANCH_TYPE_NONE;
        mem_access_width <= MEM_ACCESS_WIDTH_32;
        mem_write_enable <= '0';
        rd_data_source <= RD_DATA_SOURCE_ALU_RESULT;

        case opcode is
            when INSTR_OPCODE_LUI =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                wr_addr <= rd;
                wr_en <= '1';
                rd_data_source <= RD_DATA_SOURCE_IMM;
                imm_i(31 downto 12) := instr(31 downto 12);
                imm_i(11 downto 0) := (others => '0');

            when INSTR_OPCODE_AUIPC =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                wr_addr <= rd;
                wr_en <= '1';
                rd_data_source <= RD_DATA_SOURCE_PC_IMM;

            when INSTR_OPCODE_JAL =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                wr_addr <= rd;
                wr_en <= '1';
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;
                rd_data_source <= RD_DATA_SOURCE_PC_4;

            when INSTR_OPCODE_JALR =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                wr_addr <= rd;
                wr_en <= '1';
                rd_addr1 <= rs1;
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;
                rd_data_source <= RD_DATA_SOURCE_PC_4;

            when INSTR_OPCODE_BRANCH =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                rd_addr1 <= rs1;
                rd_addr2 <= rs2;
                case funct3 is
                    when INSTR_FUNCT3_BEQ => branch_type <= BRANCH_TYPE_BEQ;
                    when INSTR_FUNCT3_BNE => branch_type <= BRANCH_TYPE_BNE;
                    when INSTR_FUNCT3_BLT => branch_type <= BRANCH_TYPE_BLT;
                    when INSTR_FUNCT3_BGE => branch_type <= BRANCH_TYPE_BGE;
                    when INSTR_FUNCT3_BLTU => branch_type <= BRANCH_TYPE_BLTU;
                    when INSTR_FUNCT3_BGEU => branch_type <= BRANCH_TYPE_BGEU;
                    when others => null;
                end case;
                pc_next_src <= PC_NEXT_SRC_PC_ALU_RES;

            when INSTR_OPCODE_LOAD =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                rd_addr1 <= rs1;
                wr_addr <= rd;
                wr_en <= '1';
                mem_access_width <= MEM_ACCESS_WIDTH_32;
                case funct3 is
                    when INSTR_FUNCT3_LB => mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_LH => mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when INSTR_FUNCT3_LW => null;  -- default width is 32 bits
                    when INSTR_FUNCT3_LBU => mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_LHU => mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when others => null;
                end case;

            when INSTR_OPCODE_STORE =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                rd_addr1 <= rs1;
                rd_addr2 <= rs2;
                mem_write_enable <= '1';
                mem_access_width <= MEM_ACCESS_WIDTH_32;
                case funct3 is
                    when INSTR_FUNCT3_SB => mem_access_width <= MEM_ACCESS_WIDTH_8;
                    when INSTR_FUNCT3_SH => mem_access_width <= MEM_ACCESS_WIDTH_16;
                    when INSTR_FUNCT3_SW => null;  -- default width is 32 bits
                    when others => null;
                end case;

            when INSTR_OPCODE_REG_IMM =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                rd_addr1 <= rs1;
                wr_addr <= rd;
                wr_en <= '1';
                case funct3 is
                    when INSTR_FUNCT3_ADDI => alu_op_type <= ALU_OP_TYPE_ADD;
                    when INSTR_FUNCT3_SLTI => alu_op_type <= ALU_OP_TYPE_SLT;
                    when INSTR_FUNCT3_SLTIU => alu_op_type <= ALU_OP_TYPE_SLTU;
                    when INSTR_FUNCT3_XORI => alu_op_type <= ALU_OP_TYPE_XOR;
                    when INSTR_FUNCT3_ORI => alu_op_type <= ALU_OP_TYPE_OR;
                    when INSTR_FUNCT3_ANDI => alu_op_type <= ALU_OP_TYPE_AND;
                    when INSTR_FUNCT3_SLLI =>
                        if funct7 = INSTR_FUNCT7_SLLI then
                            alu_op_type <= ALU_OP_TYPE_SLL;
                        end if;
                    when INSTR_FUNCT3_SRLI | INSTR_FUNCT3_SRAI =>
                        if funct7 = INSTR_FUNCT7_SRLI then
                            alu_op_type <= ALU_OP_TYPE_SRL;
                        elsif funct7 = INSTR_FUNCT7_SRAI then
                            alu_op_type <= ALU_OP_TYPE_SRA;
                        end if;
                    when others => null;
                end case;

            when INSTR_OPCODE_REG_REG =>
                alu_op_type <= ALU_OP_TYPE_ADD;
                rd_addr1 <= rs1;
                rd_addr2 <= rs2;
                wr_addr <= rd;
                wr_en <= '1';
                case funct3 is
                    when INSTR_FUNCT3_ADD => alu_op_type <= ALU_OP_TYPE_ADD;
                    when INSTR_FUNCT3_SUB =>
                        if funct7 = INSTR_FUNCT7_SUB then
                            alu_op_type <= ALU_OP_TYPE_SUB;
                        end if;
                    when INSTR_FUNCT3_SLT => alu_op_type <= ALU_OP_TYPE_SLT;
                    when INSTR_FUNCT3_SLTU => alu_op_type <= ALU_OP_TYPE_SLTU;
                    when INSTR_FUNCT3_XOR => alu_op_type <= ALU_OP_TYPE_XOR;
                    when INSTR_FUNCT3_OR => alu_op_type <= ALU_OP_TYPE_OR;
                    when INSTR_FUNCT3_AND => alu_op_type <= ALU_OP_TYPE_AND;
                    when INSTR_FUNCT3_SLL =>
                        if funct7 = INSTR_FUNCT7_SLL then
                            alu_op_type <= ALU_OP_TYPE_SLL;
                        end if;
                    when INSTR_FUNCT3_SRL | INSTR_FUNCT3_SRA =>
                        if funct7 = INSTR_FUNCT7_SRL then
                            alu_op_type <= ALU_OP_TYPE_SRL;
                        elsif funct7 = INSTR_FUNCT7_SRA then
                            alu_op_type <= ALU_OP_TYPE_SRA;
                        end if;
                    when others => null;
                end case;

            when INSTR_OPCODE_FENCE =>
                -- FENCE instruction is not implemented

            when INSTR_OPCODE_SYSTEM =>
                -- ECALL and EBREAK instructions are not implemented

            when others =>
                alu_op_type <= ALU_OP_TYPE_ADD;  -- Default value
        end case;
    end process;

end Behavioral;
