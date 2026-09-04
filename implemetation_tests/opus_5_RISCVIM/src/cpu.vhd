-- =============================================================================
-- cpu.vhd -- rv32im_sc top level (RISC-V RV32IM, single-cycle)
-- REQ: FR-05, FR-08, FR-09, FR-10
--
-- One instruction is fetched, executed and retired per rising clock edge
-- (FR-05, CPI = 1). No pipeline registers, no stall and no forwarding: the
-- rubric fixes estagios_pipeline = 1, and the area saved is the NFR-01
-- argument for it.
--
-- Verification interface (FR-10 / pipeline:FR-17):
--   clk, rst                  -- synchronous, active-high reset
--   dbg_pc, dbg_instr         -- PC and word of the instruction retired on
--                                this edge (registered, so the testbench
--                                samples them right after the edge)
--   dbg_valid                 -- '1' only when a real instruction retired
--   data_ram_inst.memory      -- data RAM as a signal, direct child instance
--
-- Retirement trace (not fetch trace) is what makes dynamic coverage honest:
-- in this microarchitecture every fetched instruction does retire, but the
-- contract is the same one a pipelined CPU has to honour, so the golden test
-- fixture stays portable across designs.
-- =============================================================================

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_pkg.all;

entity cpu is
    port (
        clk       : in  std_logic;
        rst       : in  std_logic;
        dbg_pc    : out word_t;
        dbg_instr : out word_t;
        dbg_valid : out std_logic
    );
end entity cpu;

architecture rtl of cpu is
    -- fetch / control flow
    signal pc        : word_t;
    signal next_pc   : word_t;
    signal pc_plus_4 : word_t;
    signal instr     : word_t;

    -- control
    signal reg_write     : std_logic;
    signal mem_write     : std_logic;
    signal mem_write_gtd : std_logic;
    signal mem_to_reg    : std_logic;
    signal alu_src_a_pc  : std_logic;
    signal alu_src_b_imm : std_logic;
    signal alu_op        : std_logic_vector(3 downto 0);
    signal md_op         : std_logic_vector(2 downto 0);
    signal use_mul_div   : std_logic;
    signal imm_format    : std_logic_vector(2 downto 0);
    signal is_branch     : std_logic;
    signal is_jal        : std_logic;
    signal is_jalr       : std_logic;
    signal link_pc       : std_logic;
    signal illegal       : std_logic;  -- kept for waveform triage (FR-14)

    -- datapath
    signal imm         : word_t;
    signal rs1_data    : word_t;
    signal rs2_data    : word_t;
    signal alu_a       : word_t;
    signal alu_b       : word_t;
    signal alu_result  : word_t;
    signal md_result   : word_t;
    signal rd_data     : word_t;
    signal take_branch : std_logic;

    -- memory interface
    signal rom_data_out  : word_t;
    signal rom_data_vld  : std_logic;
    signal ram_data_out  : word_t;
    signal ram_addr_vld  : std_logic;
    signal ram_we        : std_logic;
    signal ram_be        : std_logic_vector(3 downto 0);
    signal ram_data_in   : word_t;
    signal load_result   : word_t;
begin

    -- =====================================================================
    -- Fetch -- REQ: FR-05, FR-06
    -- =====================================================================
    pc_inst : entity work.program_counter
        port map (
            clk     => clk,
            rst     => rst,
            next_pc => next_pc,
            pc      => pc
        );

    rom_inst : entity work.instruction_rom
        port map (
            instr_addr => pc,
            instr_out  => instr,
            data_addr  => alu_result,
            data_out   => rom_data_out,
            data_valid => rom_data_vld
        );

    pc_plus_4 <= std_logic_vector(unsigned(pc) + 4);

    -- =====================================================================
    -- Decode -- REQ: FR-03, FR-04, FR-14
    -- =====================================================================
    control_inst : entity work.control_unit
        port map (
            instr         => instr,
            reg_write     => reg_write,
            mem_write     => mem_write,
            mem_to_reg    => mem_to_reg,
            alu_src_a_pc  => alu_src_a_pc,
            alu_src_b_imm => alu_src_b_imm,
            alu_op        => alu_op,
            md_op         => md_op,
            use_mul_div   => use_mul_div,
            imm_format    => imm_format,
            is_branch     => is_branch,
            is_jal        => is_jal,
            is_jalr       => is_jalr,
            link_pc       => link_pc,
            illegal       => illegal
        );

    imm_inst : entity work.immediate_generator
        port map (
            instr      => instr,
            imm_format => imm_format,
            imm        => imm
        );

    regfile_inst : entity work.register_file
        port map (
            clk          => clk,
            rst          => rst,
            rs1_addr     => instr(19 downto 15),
            rs2_addr     => instr(24 downto 20),
            rd_addr      => instr(11 downto 7),
            rd_data      => rd_data,
            write_enable => reg_write,
            rs1_data     => rs1_data,
            rs2_data     => rs2_data
        );

    -- =====================================================================
    -- Execute -- REQ: FR-03, FR-04, FR-08, FR-12
    -- =====================================================================
    -- REQ: FR-08 -- with alu_src_a_pc the ALU computes pc + imm, which is the
    -- target of jal and of every branch; that reuse is why no second adder
    -- is needed (NFR-01).
    alu_a <= pc       when alu_src_a_pc = '1'  else rs1_data;
    alu_b <= imm      when alu_src_b_imm = '1' else rs2_data;

    alu_inst : entity work.alu
        port map (
            a      => alu_a,
            b      => alu_b,
            alu_op => alu_op,
            result => alu_result
        );

    muldiv_inst : entity work.mul_div_unit
        port map (
            a      => rs1_data,
            b      => rs2_data,
            md_op  => md_op,
            result => md_result
        );

    branch_inst : entity work.branch_unit
        port map (
            rs1_data    => rs1_data,
            rs2_data    => rs2_data,
            funct3      => instr(14 downto 12),
            is_branch   => is_branch,
            take_branch => take_branch
        );

    -- =====================================================================
    -- Memory -- REQ: FR-06, FR-07, FR-10
    -- =====================================================================
    -- REQ: FR-09 -- no memory side effect while reset is asserted
    mem_write_gtd <= mem_write and (not rst);

    -- REQ: FR-10 -- data_ram_inst is a direct child of the top level and its
    -- `memory` signal is the RAM state the testbench compares (FR-23).
    data_ram_inst : entity work.data_ram
        port map (
            clk          => clk,
            addr         => alu_result,
            write_enable => ram_we,
            byte_enable  => ram_be,
            data_in      => ram_data_in,
            data_out     => ram_data_out,
            addr_valid   => ram_addr_vld
        );

    lsu_inst : entity work.load_store_unit
        port map (
            addr             => alu_result,
            funct3           => instr(14 downto 12),
            mem_write        => mem_write_gtd,
            store_data       => rs2_data,
            ram_data         => ram_data_out,
            ram_valid        => ram_addr_vld,
            rom_data         => rom_data_out,
            rom_valid        => rom_data_vld,
            ram_write_enable => ram_we,
            ram_byte_enable  => ram_be,
            ram_data_in      => ram_data_in,
            load_result      => load_result
        );

    -- =====================================================================
    -- Write-back -- REQ: FR-03, FR-04, FR-08
    -- =====================================================================
    rd_data <= load_result when mem_to_reg  = '1' else
               pc_plus_4   when link_pc     = '1' else
               md_result   when use_mul_div = '1' else
               alu_result;

    -- =====================================================================
    -- Next PC -- REQ: FR-08
    -- =====================================================================
    -- jalr clears the least significant bit of the computed target, as the
    -- RISC-V spec requires; jal and branches reuse the ALU result (pc + imm).
    next_pc <= (alu_result(31 downto 1) & '0') when is_jalr = '1' else
               alu_result                      when is_jal  = '1' else
               alu_result                      when take_branch = '1' else
               pc_plus_4;

    -- =====================================================================
    -- Retirement trace -- REQ: FR-10 (pipeline:FR-25)
    -- =====================================================================
    process (clk)
    begin
        if rising_edge(clk) then
            if rst = '1' then
                dbg_valid <= '0';
                dbg_pc    <= (others => '0');
                dbg_instr <= (others => '0');
            else
                -- this edge is the one that commits pc/instr: register file
                -- and RAM take their new values here, so the instruction is
                -- retired and gets recorded exactly once.
                dbg_valid <= '1';
                dbg_pc    <= pc;
                dbg_instr <= instr;
            end if;
        end if;
    end process;

end architecture rtl;
