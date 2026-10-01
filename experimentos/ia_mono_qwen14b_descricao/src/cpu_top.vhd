-- REQ: FR-RV-04, FR-RV-05, FR-RV-06, FR-RV-12/FR-RV-13/FR-RV-14, FR-RV-15, FR-RV-16

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;
use work.cpu_package.all;
use work.memory_package.all;

entity cpu_top is
    generic(
        ROM_INIT_FILE  : string  := "";
        ROM_SIZE_WORDS : integer := 0;
        RV32M_ENABLE   : boolean := false
    );
    port(
        rst : in std_logic;   -- asynchronous, ACTIVE HIGH
        clk : in std_logic
    );
end cpu_top;

architecture Behavioral of cpu_top is

    signal pc            : std_logic_vector(31 downto 0);
    signal instr         : std_logic_vector(31 downto 0);
    signal alu_op_type   : ALU_OP_TYPE_t;
    signal reg_write_enable : std_logic;
    signal write_register : std_logic_vector(4 downto 0);
    signal read_register1 : std_logic_vector(4 downto 0);
    signal read_register2 : std_logic_vector(4 downto 0);
    signal mem_access_width : MEM_ACCESS_WIDTH_t;
    signal mem_write_enable : std_logic;
    signal pc_next_src   : PC_NEXT_SRC_t;
    signal branch_type   : BRANCH_TYPE_t;
    signal immediate_value : std_logic_vector(31 downto 0);
    signal alu_result    : std_logic_vector(31 downto 0);
    signal mem_data_out  : std_logic_vector(31 downto 0);
    signal m_dispatch    : std_logic;

begin

    -- Instantiate instruction memory
    instruction_memory : entity work.instruction_memory
        generic map (
            ROM_INIT_FILE   => ROM_INIT_FILE,
            ROM_SIZE_WORDS  => ROM_SIZE_WORDS
        )
        port map (
            addr        => pc,
            instr       => instr
        );

    -- Instantiate data memory
    data_memory : entity work.data_memory
        port map (
            clk                 => clk,
            addr                => alu_result,
            mem_write_enable    => mem_write_enable,
            access_width        => mem_access_width,
            data_in             => read_register2,

            data_out            => mem_data_out
        );

    -- Instantiate register file
    register_file : entity work.register_file
        port map (
            clk             => clk,
            rst             => rst, -- synchronous reset, ACTIVE LOW
            reg_write_enable  => reg_write_enable,
            write_register  => write_register,
            read_register1  => read_register1,
            read_register2  => read_register2,
            data_in         => alu_result,
            data_out1       => open,
            data_out2       => open
        );

    -- Instantiate ALU
    alu_inst : entity work.alu
        port map (
            op1         => read_register1,
            op2         => immediate_value,  -- Use the immediate value for OP2
            alu_op_type => alu_op_type,
            result      => alu_result
        );

    -- Instantiate decoder
    decoder_inst : entity work.decoder
        port map (
            instr         => instr,
            alu_op_type   => alu_op_type,
            reg_write_enable => reg_write_enable,
            write_register => write_register,
            read_register1 => read_register1,
            read_register2 => read_register2,
            mem_access_width => mem_access_width,
            mem_write_enable => mem_write_enable,
            pc_next_src   => pc_next_src,
            branch_type   => branch_type
        );

    -- Instantiate immediate generator
    immediate_generator_inst : entity work.immediate_generator
        port map (
            instr         => instr,
            immediate_value => immediate_value
        );

    -- Instantiate control unit (not used in this design, but included for completeness)
    control_unit_inst : entity work.control_unit
        port map (
            instr         => instr,
            alu_op_type   => open,
            reg_write_enable => open,
            write_register => open,
            read_register1 => open,
            read_register2 => open,
            mem_access_width => open,
            mem_write_enable => open,
            pc_next_src   => open,
            branch_type   => open
        );

    -- Instantiate M extension unit if RV32M_ENABLE is true
    m_extension_unit : if RV32M_ENABLE generate
        m_dispatch <= '1' when alu_op_type >= ALU_OP_TYPE_MUL else '0';
        mul_div_unit_inst : entity work.mul_div_unit
            port map (
                op1         => read_register1,
                op2         => read_register2,  -- Use the second register for OP2 in M extension
                op_type     => alu_op_type,
                start       => m_dispatch,
                res         => alu_result,
                busy        => open
            );
    end generate;

    -- PC logic
    process(clk, rst)
    begin
        if rst = '1' then
            pc <= std_logic_vector(to_unsigned(RESET_HANDLER_ADDRESS, 32));
        elsif rising_edge(clk) then
            case pc_next_src is
                when PC_NEXT_SRC_PC_ALU_RES =>
                    pc <= alu_result;
                when PC_NEXT_SRC_PC_IMM =>
                    pc <= immediate_value(31 downto 0);
                when PC_NEXT_SRC_PC_4 =>
                    pc <= std_logic_vector(unsigned(pc) + 4);
            end case;
        end if;
    end process;

end Behavioral;
