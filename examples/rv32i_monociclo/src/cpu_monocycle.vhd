-- Project      : SpecHDL / trilha RISC-V -- exemplo "CPU escrita do zero"
-- File         : cpu_monocycle.vhd
-- Description  : Single-cycle RV32I (optionally RV32IM) CPU -- top level.
--                One instruction per clock cycle: no pipeline, no hazard unit,
--                no forwarding, no stall. The program counter is the only
--                sequential element of the core itself; everything else in the
--                datapath is combinational and settles within the cycle.
--
-- REQ: FR-RV-03, FR-RV-04, FR-RV-05, FR-RV-06, FR-RV-09, FR-RV-10,
--      FR-RV-12, FR-RV-15, FR-RV-16, FR-RV-17
--
-- Why this core exists
-- --------------------
-- It is the second CPU of the track, and it has two jobs:
--   (a) it is the "student writes one from scratch" starting point;
--   (b) it is the proof that the conformance mechanism is not secretly tied to
--       the 5-stage pipeline core in examples/RISCV32I. If the same suite passes
--       on both microarchitectures, the mechanism is a validator and not a
--       testbench for one design.
--
-- What is shared and what is not
-- ------------------------------
-- The MEMORIES and the RV32M unit are reused verbatim from examples/RISCV32I
-- (they are already verified, and reusing them keeps the memory map identical,
-- which is what makes the same test programs run on both cores):
--     cpu_package.vhd, memory_package.vhd, instruction_memory.vhd,
--     data_ram.vhd, data_rom.vhd, data_memory.vhd, mul_div_unit.vhd
-- The DATAPATH and the CONTROL are written from scratch here:
--     mono_alu.vhd, mono_control.vhd, mono_regfile.vhd, this file.
--
-- Timing contract of one cycle
-- ----------------------------
--   pc (register)
--     -> instruction_memory (asynchronous read)
--     -> mono_control (combinational decode)
--     -> mono_regfile (asynchronous read) / mono_alu / mul_div_unit
--     -> data_memory (asynchronous read, synchronous write)
--     -> writeback mux
--   and at the RISING edge, all at once: pc <= pc_next, the register file
--   commits rd, and the data RAM commits a store. Every one of those uses
--   values computed from the state that existed at the START of the cycle, so
--   there is no read-after-write race inside a cycle.
--
-- Halt convention (specs/decisions.md, ADR-003): the program ends on a
-- self-loop (`halt: j halt`). In THIS core the fetch PC really does stop at
-- that address -- there is no speculative fetch to walk past it -- which is why
-- the manifest of this CPU uses `[halt] mode = "fetch_pc"` where the pipeline
-- core must use `commit_pc`.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;
use work.memory_package.all;


entity cpu_monocycle is
    generic(
        -- REQ: FR-RV-09, FR-RV-10 -- program image loaded at ELABORATION time.
        -- cocotb cannot write a GHDL ROM (ADR-003), so the image comes in by
        -- generic, exactly as in the pipeline core.
        ROM_INIT_FILE   : string  := "";     -- "" -> INSTRUCTION_MEMORY_CONTENT
        ROM_SIZE_WORDS  : integer := 0;      -- 0  -> INSTRUCTION_MEMORY_SIZE_WORDS

        -- REQ: FR-RV-16 -- false -> RV32I; true -> RV32IM
        RV32M_ENABLE    : boolean := false
    );
    port(
        rst : in std_logic;                  -- asynchronous, ACTIVE HIGH
        clk : in std_logic
    );
end cpu_monocycle;


architecture Behavioral of cpu_monocycle is

    -- ---- fetch ----------------------------------------------------------
    -- `pc` is the signal the conformance manifest observes as [halt] pc and
    -- [observe] pc_fetch. In a single-cycle core the fetch PC and the commit PC
    -- are the same thing.
    signal pc           : std_logic_vector(31 downto 0);
    signal pc_4         : std_logic_vector(31 downto 0);
    signal pc_imm       : std_logic_vector(31 downto 0);
    signal pc_jalr      : std_logic_vector(31 downto 0);
    signal pc_next      : std_logic_vector(31 downto 0);
    signal instr        : std_logic_vector(31 downto 0);

    -- ---- decode ---------------------------------------------------------
    signal rs1_select       : std_logic_vector(4 downto 0);
    signal rs2_select       : std_logic_vector(4 downto 0);
    signal rd_select        : std_logic_vector(4 downto 0);
    signal imm              : std_logic_vector(31 downto 0);
    signal alu_op_type      : ALU_OP_TYPE_t;
    signal alu_use_imm      : std_logic;
    signal rd_data_src      : RD_DATA_SOURCE_t;
    signal write_rd         : std_logic;
    signal mem_write_enable : std_logic;
    signal mem_access_width : MEM_ACCESS_WIDTH_t;
    signal is_branch        : std_logic;
    signal is_jal           : std_logic;
    signal is_jalr          : std_logic;
    signal funct3           : std_logic_vector(2 downto 0);

    -- ---- register read --------------------------------------------------
    signal rs1_data     : std_logic_vector(31 downto 0);
    signal rs2_data     : std_logic_vector(31 downto 0);

    -- ---- execute --------------------------------------------------------
    signal alu_op2      : std_logic_vector(31 downto 0);
    signal alu_result   : std_logic_vector(31 downto 0);
    signal m_result     : std_logic_vector(31 downto 0);
    signal m_busy       : std_logic;
    signal m_op         : std_logic;    -- '1' when the decoded op belongs to RV32M
    -- '1' when a REAL RV32M instruction executes this cycle. Always '0' when
    -- RV32M_ENABLE is false, so the same metric is collectable in both
    -- configurations. Exposed to the harness as [metrics] m_dispatch.
    signal m_dispatch   : std_logic;
    signal exec_result  : std_logic_vector(31 downto 0);

    -- ---- branch resolution ----------------------------------------------
    signal branch_eq    : std_logic;
    signal branch_lt    : std_logic;
    signal branch_ltu   : std_logic;
    signal branch_taken : std_logic;

    -- ---- memory / writeback ---------------------------------------------
    signal mem_data_out      : std_logic_vector(31 downto 0);
    signal mem_data_extended : std_logic_vector(31 downto 0);
    signal rd_data           : std_logic_vector(31 downto 0);

begin

    ------------------------------------------------------------------------
    -- Program counter: the single sequential element of the core.
    -- REQ: FR-RV-15 -- reset is asynchronous and active high, and lands the
    -- fetch on RESET_HANDLER_ADDRESS, same as the pipeline core.
    ------------------------------------------------------------------------
    program_counter : process(clk, rst)
    begin
        if rst = '1' then
            pc <= std_logic_vector(to_unsigned(RESET_HANDLER_ADDRESS, 32));
        elsif rising_edge(clk) then
            pc <= pc_next;
        end if;
    end process;

    pc_4   <= std_logic_vector(unsigned(pc) + 4);
    pc_imm <= std_logic_vector(unsigned(pc) + unsigned(imm));
    -- JALR clears bit 0 of the computed target, as the ISA requires
    pc_jalr <= alu_result(31 downto 1) & '0';

    pc_next <= pc_jalr when is_jalr = '1'                                   else
               pc_imm  when is_jal = '1'                                    else
               pc_imm  when is_branch = '1' and branch_taken = '1'          else
               pc_4;

    ------------------------------------------------------------------------
    -- Instruction fetch: asynchronous ROM, program supplied by generic
    -- REQ: FR-RV-09, FR-RV-10
    ------------------------------------------------------------------------
    instruction_memory : entity work.instruction_memory(Behavioral)
        generic map(
            ROM_INIT_FILE  => ROM_INIT_FILE,
            ROM_SIZE_WORDS => ROM_SIZE_WORDS
        )
        port map(
            addr  => pc,
            instr => instr
        );

    ------------------------------------------------------------------------
    -- Decode + control
    ------------------------------------------------------------------------
    control : entity work.mono_control(Behavioral)
        generic map(
            RV32M_ENABLE => RV32M_ENABLE
        )
        port map(
            instr            => instr,
            rs1_select       => rs1_select,
            rs2_select       => rs2_select,
            rd_select        => rd_select,
            imm              => imm,
            alu_op_type      => alu_op_type,
            alu_use_imm      => alu_use_imm,
            rd_data_src      => rd_data_src,
            write_rd         => write_rd,
            mem_write_enable => mem_write_enable,
            mem_access_width => mem_access_width,
            is_branch        => is_branch,
            is_jal           => is_jal,
            is_jalr          => is_jalr,
            funct3           => funct3
        );

    ------------------------------------------------------------------------
    -- Register file
    -- The instance label is `register_file` because the conformance manifest
    -- observes `register_file.registers` (FR-RV-06).
    ------------------------------------------------------------------------
    register_file : entity work.mono_regfile(Behavioral)
        port map(
            clk        => clk,
            rst        => rst,
            rs1_select => rs1_select,
            rs2_select => rs2_select,
            rd_select  => rd_select,
            rd_data    => rd_data,
            write_rd   => write_rd,
            rs1        => rs1_data,
            rs2        => rs2_data
        );

    ------------------------------------------------------------------------
    -- Execute
    ------------------------------------------------------------------------
    alu_op2 <= imm when alu_use_imm = '1' else rs2_data;

    alu : entity work.mono_alu(Behavioral)
        port map(
            op1     => rs1_data,
            op2     => alu_op2,
            op_type => alu_op_type,
            res     => alu_result
        );

    -- RV32M standard extension (REQ: FR-RV-12, FR-RV-17)
    --
    -- mul_div_unit.vhd is reused verbatim from the pipeline core. It is purely
    -- combinational, so in a single-cycle machine an M instruction costs
    -- exactly one cycle, like every other instruction: the extension changes
    -- area and critical path, never the cycle count. That is the same
    -- trade-off the pipeline core makes (ADR-007), which is what keeps the two
    -- cores comparable.
    m_op       <= '1' when is_rv32m_op(alu_op_type) else '0';
    m_dispatch <= m_op and write_rd;

    gen_rv32m : if RV32M_ENABLE generate
        mul_div_unit : entity work.mul_div_unit(Behavioral)
            port map(
                op1     => rs1_data,
                op2     => rs2_data,
                op_type => alu_op_type,
                start   => m_dispatch,
                res     => m_result,
                busy    => m_busy
            );
    end generate;

    gen_no_rv32m : if not RV32M_ENABLE generate
        m_result <= (others => '0');
        m_busy   <= '0';
    end generate;

    exec_result <= m_result when RV32M_ENABLE and is_rv32m_op(alu_op_type) else alu_result;

    ------------------------------------------------------------------------
    -- Branch resolution
    --
    -- Resolved in the SAME cycle as the fetch, which is the whole reason this
    -- core needs no speculation, no flush and no branch penalty -- and the
    -- reason its halt detection can simply watch the fetch PC.
    ------------------------------------------------------------------------
    branch_eq  <= '1' when rs1_data = rs2_data                       else '0';
    branch_lt  <= '1' when signed(rs1_data) < signed(rs2_data)       else '0';
    branch_ltu <= '1' when unsigned(rs1_data) < unsigned(rs2_data)   else '0';

    branch_taken <=     branch_eq   when funct3 = "000" else      -- BEQ
                    not branch_eq   when funct3 = "001" else      -- BNE
                        branch_lt   when funct3 = "100" else      -- BLT
                    not branch_lt   when funct3 = "101" else      -- BGE
                        branch_ltu  when funct3 = "110" else      -- BLTU
                    not branch_ltu  when funct3 = "111" else      -- BGEU
                    '0';                                          -- 010/011: undefined

    ------------------------------------------------------------------------
    -- Data memory
    -- The instance label is `data_memory` because the conformance manifest
    -- observes `data_memory.data_ram.memory` (FR-RV-06). The wrapper already
    -- routes DATA_ROM (0x00FC8000) and DATA_RAM (0x00FC8100) by absolute
    -- address, so the memory map is bit-for-bit the pipeline core's.
    ------------------------------------------------------------------------
    data_memory : entity work.data_memory(Behavioral)
        port map(
            clk              => clk,
            addr             => alu_result,
            mem_write_enable => mem_write_enable,
            access_width     => mem_access_width,
            data_in          => rs2_data,
            data_out         => mem_data_out
        );

    -- Load sign-extension. data_memory zero-extends bytes and halfwords, so
    -- only LB (funct3 = 000) and LH (funct3 = 001) need the sign put back;
    -- LBU, LHU and LW pass straight through.
    mem_data_extended <=
        (31 downto 7  => mem_data_out(7))  & mem_data_out(6 downto 0)   when funct3 = "000" else
        (31 downto 15 => mem_data_out(15)) & mem_data_out(14 downto 0)  when funct3 = "001" else
        mem_data_out;

    ------------------------------------------------------------------------
    -- Writeback mux
    ------------------------------------------------------------------------
    rd_data <= imm               when rd_data_src = RD_DATA_SOURCE_IMM          else  -- LUI
               pc_imm            when rd_data_src = RD_DATA_SOURCE_PC_IMM       else  -- AUIPC
               pc_4              when rd_data_src = RD_DATA_SOURCE_PC_4         else  -- JAL/JALR
               mem_data_extended when rd_data_src = RD_DATA_SOURCE_MEM_DATA_OUT else  -- loads
               exec_result;                                                           -- ALU / RV32M

end Behavioral;
