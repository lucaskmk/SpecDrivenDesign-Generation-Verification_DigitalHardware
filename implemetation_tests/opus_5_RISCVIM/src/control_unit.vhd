-- =============================================================================
-- control_unit.vhd -- hardwired combinational instruction decoder
-- REQ: FR-03, FR-04, FR-05, FR-14
--
-- The rubric fixes hardwired control (multiciclo_microprogramado = False): no
-- microcode ROM and no FSM, which saves area and memory (NFR-01) and keeps
-- decode in the same cycle as execution (NFR-02). Price paid: a wider
-- combinational decode table, acceptable for 45 fixed-format instructions.
--
-- Decoding is strict: reserved funct3/funct7 encodings are flagged as
-- illegal, and an illegal instruction produces no register write and no
-- memory write, so it behaves as a nop and execution continues at PC+4
-- (FR-14). Being strict here is what prevents an unimplemented opcode from
-- silently aliasing onto an implemented one and inflating coverage.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity control_unit is
    port (
        instr         : in  word_t;
        reg_write     : out std_logic;
        mem_write     : out std_logic;
        mem_to_reg    : out std_logic;
        alu_src_a_pc  : out std_logic;
        alu_src_b_imm : out std_logic;
        alu_op        : out std_logic_vector(3 downto 0);
        md_op         : out std_logic_vector(2 downto 0);
        use_mul_div   : out std_logic;
        imm_format    : out std_logic_vector(2 downto 0);
        is_branch     : out std_logic;
        is_jal        : out std_logic;
        is_jalr       : out std_logic;
        link_pc       : out std_logic;
        illegal       : out std_logic
    );
end entity control_unit;

architecture rtl of control_unit is
    alias opcode : std_logic_vector(6 downto 0) is instr(6 downto 0);
    alias funct3 : std_logic_vector(2 downto 0) is instr(14 downto 12);
    alias funct7 : std_logic_vector(6 downto 0) is instr(31 downto 25);
begin

    process (instr, opcode, funct3, funct7)
    begin
        -- defaults: nop (FR-14)
        reg_write     <= '0';
        mem_write     <= '0';
        mem_to_reg    <= '0';
        alu_src_a_pc  <= '0';
        alu_src_b_imm <= '0';
        alu_op        <= ALU_ADD;
        md_op         <= MD_MUL;
        use_mul_div   <= '0';
        imm_format    <= IMM_NONE;
        is_branch     <= '0';
        is_jal        <= '0';
        is_jalr       <= '0';
        link_pc       <= '0';
        illegal       <= '0';

        -- Opcode dispatch is an if/elsif chain because the opcode constants
        -- live in cpu_pkg and VHDL-93 does not accept package constants as
        -- case choices; the inner dispatches on funct3/funct7 use literals
        -- and stay as case statements.
        if opcode = OPC_LUI then
            -- REQ: FR-03 -- lui: rd <= imm_u
            reg_write     <= '1';
            imm_format    <= IMM_U;
            alu_src_b_imm <= '1';
            alu_op        <= ALU_PASS_B;

        elsif opcode = OPC_AUIPC then
            -- REQ: FR-03 -- auipc: rd <= pc + imm_u
            reg_write     <= '1';
            imm_format    <= IMM_U;
            alu_src_a_pc  <= '1';
            alu_src_b_imm <= '1';
            alu_op        <= ALU_ADD;

        elsif opcode = OPC_JAL then
            -- REQ: FR-03, FR-08 -- jal: rd <= pc+4, pc <= pc + imm_j
            reg_write     <= '1';
            imm_format    <= IMM_J;
            alu_src_a_pc  <= '1';
            alu_src_b_imm <= '1';
            alu_op        <= ALU_ADD;
            is_jal        <= '1';
            link_pc       <= '1';

        elsif opcode = OPC_JALR then
            -- REQ: FR-03, FR-08 -- jalr: rd <= pc+4, pc <= (rs1+imm) & ~1
            if funct3 = "000" then
                reg_write     <= '1';
                imm_format    <= IMM_I;
                alu_src_b_imm <= '1';
                alu_op        <= ALU_ADD;
                is_jalr       <= '1';
                link_pc       <= '1';
            else
                illegal <= '1';
            end if;

        elsif opcode = OPC_BRANCH then
            -- REQ: FR-03, FR-08 -- branches; the ALU computes pc + imm_b
            case funct3 is
                when "000" | "001" | "100" | "101" | "110" | "111" =>
                    imm_format    <= IMM_B;
                    alu_src_a_pc  <= '1';
                    alu_src_b_imm <= '1';
                    alu_op        <= ALU_ADD;
                    is_branch     <= '1';
                when others =>
                    illegal <= '1';
            end case;

        elsif opcode = OPC_LOAD then
            -- REQ: FR-03, FR-07 -- loads; the ALU computes rs1 + imm_i
            case funct3 is
                when "000" | "001" | "010" | "100" | "101" =>
                    reg_write     <= '1';
                    mem_to_reg    <= '1';
                    imm_format    <= IMM_I;
                    alu_src_b_imm <= '1';
                    alu_op        <= ALU_ADD;
                when others =>
                    illegal <= '1';  -- lwu/ld are RV64 (FR-14)
            end case;

        elsif opcode = OPC_STORE then
            -- REQ: FR-03, FR-07 -- stores; the ALU computes rs1 + imm_s
            case funct3 is
                when "000" | "001" | "010" =>
                    mem_write     <= '1';
                    imm_format    <= IMM_S;
                    alu_src_b_imm <= '1';
                    alu_op        <= ALU_ADD;
                when others =>
                    illegal <= '1';  -- sd is RV64 (FR-14)
            end case;

        elsif opcode = OPC_OP_IMM then
            -- REQ: FR-03, FR-12 -- register/immediate ALU operations
            reg_write     <= '1';
            imm_format    <= IMM_I;
            alu_src_b_imm <= '1';
            case funct3 is
                when "000" => alu_op <= ALU_ADD;   -- addi
                when "010" => alu_op <= ALU_SLT;   -- slti
                when "011" => alu_op <= ALU_SLTU;  -- sltiu
                when "100" => alu_op <= ALU_XOR;   -- xori
                when "110" => alu_op <= ALU_OR;    -- ori
                when "111" => alu_op <= ALU_AND;   -- andi
                when "001" =>                      -- slli
                    if funct7 = "0000000" then
                        alu_op <= ALU_SLL;
                    else
                        reg_write <= '0';
                        illegal   <= '1';
                    end if;
                when others =>                     -- "101": srli / srai
                    if funct7 = "0000000" then
                        alu_op <= ALU_SRL;
                    elsif funct7 = "0100000" then
                        alu_op <= ALU_SRA;
                    else
                        reg_write <= '0';
                        illegal   <= '1';
                    end if;
            end case;

        elsif opcode = OPC_OP then
            -- REQ: FR-03, FR-04 -- register/register operations, incl. M
            reg_write <= '1';
            case funct7 is
                when "0000000" =>
                    case funct3 is
                        when "000" => alu_op <= ALU_ADD;   -- add
                        when "001" => alu_op <= ALU_SLL;   -- sll
                        when "010" => alu_op <= ALU_SLT;   -- slt
                        when "011" => alu_op <= ALU_SLTU;  -- sltu
                        when "100" => alu_op <= ALU_XOR;   -- xor
                        when "101" => alu_op <= ALU_SRL;   -- srl
                        when "110" => alu_op <= ALU_OR;    -- or
                        when others => alu_op <= ALU_AND;  -- and
                    end case;
                when "0100000" =>
                    case funct3 is
                        when "000" => alu_op <= ALU_SUB;   -- sub
                        when "101" => alu_op <= ALU_SRA;   -- sra
                        when others =>
                            reg_write <= '0';
                            illegal   <= '1';
                    end case;
                when "0000001" =>
                    -- REQ: FR-04 -- M extension; md_op is funct3 verbatim
                    use_mul_div <= '1';
                    md_op       <= funct3;
                when others =>
                    reg_write <= '0';
                    illegal   <= '1';
            end case;

        else
            -- REQ: FR-14 -- everything else (incl. fence/ecall/ebreak/CSR)
            illegal <= '1';
        end if;
    end process;

end architecture rtl;
