-- Project      : SpecHDL / trilha RISC-V -- exemplo "CPU escrita do zero"
-- File         : mono_control.vhd
-- Description  : Instruction decoder + control unit of the single-cycle core.
--                One combinational block turns the 32-bit instruction word into
--                register selects, the sign-extended immediate and every control
--                signal the datapath needs.
--
-- REQ: FR-RV-03, FR-RV-04, FR-RV-05, FR-RV-12, FR-RV-13, FR-RV-16
--
-- Design notes
-- ------------
-- 1. ONE BLOCK, NOT THREE. The pipeline core splits this job across
--    instruction_decoder.vhd, control_unit.vhd and extend_32.vhd because each
--    piece feeds a different pipeline stage. A single-cycle core has no stages,
--    so decoding is one flat combinational function of the fetched word. This
--    is a real microarchitectural difference, not a cosmetic one.
--
-- 2. RV32M IS GATED BY A GENERIC. Every RV32M instruction shares opcode
--    REG_REG and its funct3 with an RV32I instruction; only funct7 = 0000001
--    tells them apart. That arm is therefore tested FIRST, and only when
--    RV32M_ENABLE is true -- with the generic false the decoding is exactly
--    RV32I, so the same source tree serves both configurations (FR-RV-16).
--
-- 3. UNKNOWN OPCODES ARE INERT. FENCE, ECALL/EBREAK and any undefined encoding
--    (including the 0xFFFFFFFF an out-of-range fetch returns) fall into the
--    `others` arm, which writes no register and no memory. The target CPU of
--    this track does not implement them either, so the two cores agree.
--
-- 4. LITERALS IN CASE CHOICES. The bit patterns below are written as literals
--    rather than as the named constants of cpu_package.vhd because VHDL case
--    choices must be locally static, and a package constant is not portably so.
--    The mnemonic is spelled out in a comment on every arm.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;


entity mono_control is
    generic(
        -- false -> pure RV32I decoding; true -> RV32I + the eight M instructions
        RV32M_ENABLE : boolean := false
    );
    port(
        instr            : in  std_logic_vector(31 downto 0);

        -- register file interface
        rs1_select       : out std_logic_vector(4 downto 0);
        rs2_select       : out std_logic_vector(4 downto 0);
        rd_select        : out std_logic_vector(4 downto 0);

        -- sign-extended immediate, already in the shape the opcode requires
        imm              : out std_logic_vector(31 downto 0);

        -- datapath control
        alu_op_type      : out ALU_OP_TYPE_t;
        alu_use_imm      : out std_logic;                    -- '1' -> ALU op2 = imm
        rd_data_src      : out RD_DATA_SOURCE_t;
        write_rd         : out std_logic;
        mem_write_enable : out std_logic;
        mem_access_width : out MEM_ACCESS_WIDTH_t;

        -- control-flow class of the instruction
        is_branch        : out std_logic;
        is_jal           : out std_logic;
        is_jalr          : out std_logic;

        -- raw funct3, used by the branch comparator and by the load
        -- sign-extension in the top level
        funct3           : out std_logic_vector(2 downto 0)
    );
end mono_control;


architecture Behavioral of mono_control is

    -- I-type immediate: sext(instr[31:20])
    function imm_i(w : std_logic_vector(31 downto 0)) return std_logic_vector is
    begin
        return std_logic_vector(resize(signed(w(31 downto 20)), 32));
    end function;

    -- S-type immediate: sext(instr[31:25] & instr[11:7])
    function imm_s(w : std_logic_vector(31 downto 0)) return std_logic_vector is
    begin
        return std_logic_vector(resize(signed(w(31 downto 25) & w(11 downto 7)), 32));
    end function;

    -- B-type immediate: sext(instr[31] & instr[7] & instr[30:25] & instr[11:8] & '0')
    function imm_b(w : std_logic_vector(31 downto 0)) return std_logic_vector is
        variable bits : std_logic_vector(12 downto 0);
    begin
        bits := w(31) & w(7) & w(30 downto 25) & w(11 downto 8) & '0';
        return std_logic_vector(resize(signed(bits), 32));
    end function;

    -- U-type immediate: instr[31:12] << 12
    function imm_u(w : std_logic_vector(31 downto 0)) return std_logic_vector is
    begin
        return w(31 downto 12) & x"000";
    end function;

    -- J-type immediate: sext(instr[31] & instr[19:12] & instr[20] & instr[30:21] & '0')
    function imm_j(w : std_logic_vector(31 downto 0)) return std_logic_vector is
        variable bits : std_logic_vector(20 downto 0);
    begin
        bits := w(31) & w(19 downto 12) & w(20) & w(30 downto 21) & '0';
        return std_logic_vector(resize(signed(bits), 32));
    end function;

    -- RV32I ALU operation carried by funct3, plus instr[30] as the ADD/SUB and
    -- SRL/SRA discriminator. `sub_allowed` is true only for R-type: on OP-IMM
    -- bit 30 selects SRAI but must NOT turn ADDI into a subtraction.
    function alu_op_from_funct3(f3          : std_logic_vector(2 downto 0);
                                bit30       : std_logic;
                                sub_allowed : boolean) return ALU_OP_TYPE_t is
    begin
        case f3 is
            when "000" =>                                   -- ADD / SUB / ADDI
                if sub_allowed and bit30 = '1' then
                    return ALU_OP_TYPE_SUB;
                else
                    return ALU_OP_TYPE_ADD;
                end if;
            when "001"  => return ALU_OP_TYPE_SLL;           -- SLL  / SLLI
            when "010"  => return ALU_OP_TYPE_SLT;           -- SLT  / SLTI
            when "011"  => return ALU_OP_TYPE_SLTU;          -- SLTU / SLTIU
            when "100"  => return ALU_OP_TYPE_XOR;           -- XOR  / XORI
            when "101"  =>                                   -- SRL/SRA, SRLI/SRAI
                if bit30 = '1' then
                    return ALU_OP_TYPE_SRA;
                else
                    return ALU_OP_TYPE_SRL;
                end if;
            when "110"  => return ALU_OP_TYPE_OR;            -- OR   / ORI
            when others => return ALU_OP_TYPE_AND;           -- AND  / ANDI
        end case;
    end function;

    -- RV32M operation carried by funct3 when funct7 = 0000001
    function alu_op_from_m_funct3(f3 : std_logic_vector(2 downto 0)) return ALU_OP_TYPE_t is
    begin
        case f3 is
            when "000"  => return ALU_OP_TYPE_MUL;
            when "001"  => return ALU_OP_TYPE_MULH;
            when "010"  => return ALU_OP_TYPE_MULHSU;
            when "011"  => return ALU_OP_TYPE_MULHU;
            when "100"  => return ALU_OP_TYPE_DIV;
            when "101"  => return ALU_OP_TYPE_DIVU;
            when "110"  => return ALU_OP_TYPE_REM;
            when others => return ALU_OP_TYPE_REMU;
        end case;
    end function;

begin

    rs1_select <= instr(19 downto 15);
    rs2_select <= instr(24 downto 20);
    rd_select  <= instr(11 downto 7);
    funct3     <= instr(14 downto 12);

    decode : process(instr)
        variable f3 : std_logic_vector(2 downto 0);
        variable f7 : std_logic_vector(6 downto 0);
    begin
        f3 := instr(14 downto 12);
        f7 := instr(31 downto 25);

        -- safe defaults: no architectural state is modified
        imm              <= imm_i(instr);
        alu_op_type      <= ALU_OP_TYPE_ADD;
        alu_use_imm      <= '0';
        rd_data_src      <= RD_DATA_SOURCE_ALU_RESULT;
        write_rd         <= '0';
        mem_write_enable <= '0';
        mem_access_width <= MEM_ACCESS_WIDTH_32;
        is_branch        <= '0';
        is_jal           <= '0';
        is_jalr          <= '0';

        case instr(6 downto 0) is

            when "0110111" =>                               -- LUI
                imm         <= imm_u(instr);
                rd_data_src <= RD_DATA_SOURCE_IMM;
                write_rd    <= '1';

            when "0010111" =>                               -- AUIPC
                imm         <= imm_u(instr);
                rd_data_src <= RD_DATA_SOURCE_PC_IMM;       -- pc + imm, built in the top
                write_rd    <= '1';

            when "1101111" =>                               -- JAL
                imm         <= imm_j(instr);
                rd_data_src <= RD_DATA_SOURCE_PC_4;
                write_rd    <= '1';
                is_jal      <= '1';

            when "1100111" =>                               -- JALR
                imm         <= imm_i(instr);
                alu_use_imm <= '1';                         -- ALU computes rs1 + imm
                rd_data_src <= RD_DATA_SOURCE_PC_4;
                write_rd    <= '1';
                is_jalr     <= '1';

            when "1100011" =>                               -- BEQ/BNE/BLT/BGE/BLTU/BGEU
                imm       <= imm_b(instr);
                is_branch <= '1';

            when "0000011" =>                               -- LB/LH/LW/LBU/LHU
                imm         <= imm_i(instr);
                alu_use_imm <= '1';                         -- address = rs1 + imm
                rd_data_src <= RD_DATA_SOURCE_MEM_DATA_OUT;
                write_rd    <= '1';
                if f3 = "010" then                          -- LW
                    mem_access_width <= MEM_ACCESS_WIDTH_32;
                elsif f3 = "001" or f3 = "101" then         -- LH / LHU
                    mem_access_width <= MEM_ACCESS_WIDTH_16;
                else                                        -- LB / LBU
                    mem_access_width <= MEM_ACCESS_WIDTH_8;
                end if;

            when "0100011" =>                               -- SB/SH/SW
                imm              <= imm_s(instr);
                alu_use_imm      <= '1';                    -- address = rs1 + imm
                mem_write_enable <= '1';
                if f3 = "010" then                          -- SW
                    mem_access_width <= MEM_ACCESS_WIDTH_32;
                elsif f3 = "001" then                       -- SH
                    mem_access_width <= MEM_ACCESS_WIDTH_16;
                else                                        -- SB
                    mem_access_width <= MEM_ACCESS_WIDTH_8;
                end if;

            when "0010011" =>                               -- OP-IMM (9 instructions)
                imm         <= imm_i(instr);
                alu_use_imm <= '1';
                write_rd    <= '1';
                alu_op_type <= alu_op_from_funct3(f3, instr(30), false);

            when "0110011" =>                               -- OP (10 RV32I + 8 RV32M)
                write_rd <= '1';
                if RV32M_ENABLE and f7 = "0000001" then
                    alu_op_type <= alu_op_from_m_funct3(f3);
                else
                    alu_op_type <= alu_op_from_funct3(f3, instr(30), true);
                end if;

            when others =>
                -- FENCE, ECALL/EBREAK and undefined encodings: inert
                null;

        end case;
    end process;

end Behavioral;
