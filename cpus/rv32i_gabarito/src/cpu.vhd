-- Reference RV32I single-cycle CPU for the virtual-bus contract of specs/cpu.md.
--
-- One instruction completes per rising edge of clk. There are no memories in
-- this file: the validator supplies the ROM and the RAM through the ports, so
-- the instruction word arrives on instr_data and load data on data_read_data.
--
-- Timing of one cycle:
--   pc (register) -> instr_addr -> [validator ROM] -> instr_data
--     -> decode -> register read -> ALU / address adder -> data_addr
--     -> [validator RAM, asynchronous read] -> data_read_data -> write-back mux
--   and at the rising edge: pc <= pc_next, the register file commits rd, and
--   the validator RAM commits a store (data_write = '1').
--
-- Not implemented (specs/cpu.md): FENCE, ECALL, EBREAK, CSRs, interrupts and
-- misaligned accesses. FENCE/ECALL/EBREAK behave as NOPs.

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity cpu is
    port(
        clk : in std_logic;
        rst : in std_logic;
        instr_addr : out std_logic_vector(31 downto 0);
        instr_data : in std_logic_vector(31 downto 0);
        data_addr : out std_logic_vector(31 downto 0);
        data_write : out std_logic;
        data_width : out std_logic_vector(1 downto 0);
        data_write_data : out std_logic_vector(31 downto 0);
        data_read_data : in std_logic_vector(31 downto 0)
    );
end cpu;

architecture rtl of cpu is

    constant OP_LUI    : std_logic_vector(6 downto 0) := "0110111";
    constant OP_AUIPC  : std_logic_vector(6 downto 0) := "0010111";
    constant OP_JAL    : std_logic_vector(6 downto 0) := "1101111";
    constant OP_JALR   : std_logic_vector(6 downto 0) := "1100111";
    constant OP_BRANCH : std_logic_vector(6 downto 0) := "1100011";
    constant OP_LOAD   : std_logic_vector(6 downto 0) := "0000011";
    constant OP_STORE  : std_logic_vector(6 downto 0) := "0100011";
    constant OP_IMM    : std_logic_vector(6 downto 0) := "0010011";
    constant OP_REG    : std_logic_vector(6 downto 0) := "0110011";

    type regfile_t is array (0 to 31) of std_logic_vector(31 downto 0);

    -- state
    signal pc   : std_logic_vector(31 downto 0) := (others => '0');
    signal regs : regfile_t := (others => (others => '0'));

    -- instruction fields (aliases: no extra delta cycle after instr_data)
    alias opcode : std_logic_vector(6 downto 0) is instr_data(6 downto 0);
    alias funct3 : std_logic_vector(2 downto 0) is instr_data(14 downto 12);

    -- immediates
    signal imm_i : std_logic_vector(31 downto 0);
    signal imm_s : std_logic_vector(31 downto 0);
    signal imm_b : std_logic_vector(31 downto 0);
    signal imm_u : std_logic_vector(31 downto 0);
    signal imm_j : std_logic_vector(31 downto 0);

    -- datapath
    signal rs1_val    : std_logic_vector(31 downto 0);
    signal rs2_val    : std_logic_vector(31 downto 0);
    signal alu_b      : std_logic_vector(31 downto 0);
    signal alu_result : std_logic_vector(31 downto 0);
    signal load_val   : std_logic_vector(31 downto 0);
    signal wb_data    : std_logic_vector(31 downto 0);
    signal reg_write  : std_logic;

    -- next pc
    signal pc_plus4      : std_logic_vector(31 downto 0);
    signal branch_target : std_logic_vector(31 downto 0);
    signal jal_target    : std_logic_vector(31 downto 0);
    signal take_branch   : std_logic;
    signal pc_next       : std_logic_vector(31 downto 0);

begin

    ------------------------------------------------------------------------
    -- Immediates. Sign extension always goes through resize(signed(...)).
    ------------------------------------------------------------------------
    imm_i <= std_logic_vector(resize(signed(instr_data(31 downto 20)), 32));
    imm_s <= std_logic_vector(resize(signed(std_logic_vector'(
                 instr_data(31 downto 25) & instr_data(11 downto 7))), 32));
    imm_b <= std_logic_vector(resize(signed(std_logic_vector'(
                 instr_data(31) & instr_data(7) & instr_data(30 downto 25) &
                 instr_data(11 downto 8) & '0')), 32));
    imm_u <= instr_data(31 downto 12) & x"000";
    imm_j <= std_logic_vector(resize(signed(std_logic_vector'(
                 instr_data(31) & instr_data(19 downto 12) & instr_data(20) &
                 instr_data(30 downto 21) & '0')), 32));

    ------------------------------------------------------------------------
    -- Register file: asynchronous reset to zero, asynchronous read, write on
    -- the rising edge. x0 is never written, so it always reads as zero.
    ------------------------------------------------------------------------
    regfile : process(clk, rst)
    begin
        if rst = '1' then
            regs <= (others => (others => '0'));
        elsif rising_edge(clk) then
            if reg_write = '1' and instr_data(11 downto 7) /= "00000" then
                regs(to_integer(unsigned(instr_data(11 downto 7)))) <= wb_data;
            end if;
        end if;
    end process regfile;

    rs1_val <= regs(to_integer(unsigned(instr_data(19 downto 15))));
    rs2_val <= regs(to_integer(unsigned(instr_data(24 downto 20))));

    ------------------------------------------------------------------------
    -- ALU. OP-IMM uses the I immediate as the second operand. Only the OP
    -- opcode can subtract: for OP-IMM, instr(30) is an immediate bit (ADDI).
    ------------------------------------------------------------------------
    alu_b <= imm_i when opcode = OP_IMM else rs2_val;

    alu : process(all)
        variable shamt : integer range 0 to 31;
    begin
        shamt := to_integer(unsigned(alu_b(4 downto 0)));
        alu_result <= (others => '0');
        case funct3 is
            when "000" =>
                if opcode = OP_REG and instr_data(30) = '1' then
                    alu_result <= std_logic_vector(unsigned(rs1_val) - unsigned(alu_b));
                else
                    alu_result <= std_logic_vector(unsigned(rs1_val) + unsigned(alu_b));
                end if;
            when "001" =>
                alu_result <= std_logic_vector(shift_left(unsigned(rs1_val), shamt));
            when "010" =>
                if signed(rs1_val) < signed(alu_b) then
                    alu_result <= x"00000001";
                end if;
            when "011" =>
                if unsigned(rs1_val) < unsigned(alu_b) then
                    alu_result <= x"00000001";
                end if;
            when "100" =>
                alu_result <= rs1_val xor alu_b;
            when "101" =>
                if instr_data(30) = '1' then
                    alu_result <= std_logic_vector(shift_right(signed(rs1_val), shamt));
                else
                    alu_result <= std_logic_vector(shift_right(unsigned(rs1_val), shamt));
                end if;
            when "110" =>
                alu_result <= rs1_val or alu_b;
            when others =>
                alu_result <= rs1_val and alu_b;
        end case;
    end process alu;

    ------------------------------------------------------------------------
    -- Data bus. data_addr is the effective byte address (rs1 + I for loads,
    -- rs1 + S for stores), never masked. data_write_data carries rs2 as is:
    -- the validator uses its low 8, 16 or 32 bits according to data_width.
    ------------------------------------------------------------------------
    data_addr <= std_logic_vector(unsigned(rs1_val) + unsigned(imm_s)) when opcode = OP_STORE
                 else std_logic_vector(unsigned(rs1_val) + unsigned(imm_i));
    data_write      <= '1' when opcode = OP_STORE and rst = '0' else '0';
    data_write_data <= rs2_val;
    data_width      <= funct3(1 downto 0) when opcode = OP_LOAD or opcode = OP_STORE else "10";

    -- Load: pick the byte or halfword out of the word at data_addr(31:2) and
    -- extend it (LB/LH with sign, LBU/LHU with zero, LW as is).
    load_select : process(all)
        variable byte_v : std_logic_vector(7 downto 0);
        variable half_v : std_logic_vector(15 downto 0);
    begin
        case data_addr(1 downto 0) is
            when "00"   => byte_v := data_read_data(7 downto 0);
            when "01"   => byte_v := data_read_data(15 downto 8);
            when "10"   => byte_v := data_read_data(23 downto 16);
            when others => byte_v := data_read_data(31 downto 24);
        end case;
        if data_addr(1) = '1' then
            half_v := data_read_data(31 downto 16);
        else
            half_v := data_read_data(15 downto 0);
        end if;
        case funct3 is
            when "000"  => load_val <= std_logic_vector(resize(signed(byte_v), 32));
            when "001"  => load_val <= std_logic_vector(resize(signed(half_v), 32));
            when "100"  => load_val <= std_logic_vector(resize(unsigned(byte_v), 32));
            when "101"  => load_val <= std_logic_vector(resize(unsigned(half_v), 32));
            when others => load_val <= data_read_data;
        end case;
    end process load_select;

    ------------------------------------------------------------------------
    -- Write-back
    ------------------------------------------------------------------------
    reg_write <= '1' when opcode = OP_LUI or opcode = OP_AUIPC or opcode = OP_JAL or
                          opcode = OP_JALR or opcode = OP_LOAD or opcode = OP_IMM or
                          opcode = OP_REG
                 else '0';

    wb_data <= imm_u                                                       when opcode = OP_LUI   else
               std_logic_vector(unsigned(pc) + unsigned(imm_u))            when opcode = OP_AUIPC else
               pc_plus4                                                    when opcode = OP_JAL or opcode = OP_JALR else
               load_val                                                    when opcode = OP_LOAD  else
               alu_result;

    ------------------------------------------------------------------------
    -- Program counter. Reset is asynchronous and active high. Priority of the
    -- next pc: JAL/JALR, taken branch, pc + 4. JAL x0, 0 keeps the pc.
    ------------------------------------------------------------------------
    pc_plus4      <= std_logic_vector(unsigned(pc) + 4);
    branch_target <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
    jal_target    <= std_logic_vector(unsigned(pc) + unsigned(imm_j));

    take_branch <= '1' when (funct3 = "000" and rs1_val = rs2_val) or
                            (funct3 = "001" and rs1_val /= rs2_val) or
                            (funct3 = "100" and signed(rs1_val) < signed(rs2_val)) or
                            (funct3 = "101" and signed(rs1_val) >= signed(rs2_val)) or
                            (funct3 = "110" and unsigned(rs1_val) < unsigned(rs2_val)) or
                            (funct3 = "111" and unsigned(rs1_val) >= unsigned(rs2_val))
                   else '0';

    pc_next <= jal_target                                                        when opcode = OP_JAL    else
               data_addr(31 downto 1) & '0'                                      when opcode = OP_JALR   else
               branch_target                                                     when opcode = OP_BRANCH and take_branch = '1' else
               pc_plus4;

    program_counter : process(clk, rst)
    begin
        if rst = '1' then
            pc <= (others => '0');
        elsif rising_edge(clk) then
            pc <= pc_next;
        end if;
    end process program_counter;

    instr_addr <= pc;

end rtl;
