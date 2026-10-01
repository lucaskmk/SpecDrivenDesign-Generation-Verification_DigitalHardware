-- src/cpu_top.vhd

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
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

    signal pc              : std_logic_vector(31 downto 0);
    signal instr           : std_logic_vector(31 downto 0);
    signal alu_op_type     : ALU_OP_TYPE_t;
    signal rd_addr1        : std_logic_vector(4 downto 0);
    signal rd_addr2        : std_logic_vector(4 downto 0);
    signal wr_addr         : std_logic_vector(4 downto 0);
    signal wr_data         : std_logic_vector(31 downto 0);
    signal wr_en           : std_logic;
    signal pc_next_src     : PC_NEXT_SRC_t;
    signal branch_type     : BRANCH_TYPE_t;
    signal mem_access_width: MEM_ACCESS_WIDTH_t;
    signal mem_write_enable: std_logic;
    signal rd_data_source  : RD_DATA_SOURCE_t;
    signal alu_result      : std_logic_vector(31 downto 0);
    signal mem_data_out    : std_logic_vector(31 downto 0);
    signal m_dispatch      : std_logic;
    signal rd_data1        : std_logic_vector(31 downto 0);
    signal rd_data2        : std_logic_vector(31 downto 0);

begin

    -- Instantiate instruction_memory
    instruction_memory_inst: entity work.instruction_memory
        generic map (
            ROM_INIT_FILE   => ROM_INIT_FILE,
            ROM_SIZE_WORDS  => ROM_SIZE_WORDS
        )
        port map (
            addr        => pc,
            instr       => instr
        );

    -- Instantiate data_memory
    data_memory_inst: entity work.data_memory
        port map (
            clk                 => clk,
            addr                => alu_result,
            mem_write_enable    => mem_write_enable,
            access_width        => mem_access_width,
            data_in             => rd_data1,

            data_out            => mem_data_out
        );

    -- Instantiate register_file
    register_file_inst: entity work.register_file
        port map (
            clk         => clk,
            rst         => rst,
            rd_addr1    => rd_addr1,
            rd_addr2    => rd_addr2,
            wr_addr     => wr_addr,
            wr_data     => wr_data,
            wr_en       => wr_en,
            rd_data1    => rd_data1,
            rd_data2    => rd_data2
        );

    -- Instantiate alu
    alu_inst: entity work.alu
        port map (
            op1         => rd_data1,
            op2         => rd_data2,
            alu_op_type => alu_op_type,
            result      => alu_result
        );

    -- Instantiate decoder
    decoder_inst: entity work.decoder
        port map (
            instr             => instr,
            alu_op_type       => alu_op_type,
            rd_addr1          => rd_addr1,
            rd_addr2          => rd_addr2,
            wr_addr           => wr_addr,
            wr_en             => wr_en,
            pc_next_src       => pc_next_src,
            branch_type       => branch_type,
            mem_access_width  => mem_access_width,
            mem_write_enable  => mem_write_enable,
            rd_data_source    => rd_data_source
        );

    -- Instantiate mul_div_unit if RV32M_ENABLE is true
    m_dispatch <= '1' when RV32M_ENABLE and (alu_op_type >= ALU_OP_TYPE_MUL) else '0';
    mul_div_unit_inst: if RV32M_ENABLE generate
        mul_div_unit_gen: entity work.mul_div_unit
            port map (
                op1         => rd_data1,
                op2         => rd_data2,
                op_type     => alu_op_type,
                start       => m_dispatch,
                res         => wr_data,
                busy        => open
            );
    end generate;

    -- Combinational logic for PC update
    process(pc, instr, alu_result, branch_type, rd_data1, rd_data2)
        variable next_pc : std_logic_vector(31 downto 0);
    begin
        next_pc := std_logic_vector(unsigned(pc) + 4);  -- Default: increment by 4

        case pc_next_src is
            when PC_NEXT_SRC_PC_ALU_RES =>
                next_pc := alu_result;
            when PC_NEXT_SRC_PC_IMM =>
                next_pc := std_logic_vector(signed(pc) + signed(rd_data2));
            when PC_NEXT_SRC_PC_4 =>
                next_pc := std_logic_vector(unsigned(pc) + 4);
        end case;

        -- Branch logic
        if branch_type /= BRANCH_TYPE_NONE then
            case branch_type is
                when BRANCH_TYPE_BEQ =>
                    if rd_data1 = rd_data2 then
                        next_pc := std_logic_vector(signed(pc) + signed(rd_data2));
                    end if;
                when BRANCH_TYPE_BNE =>
                    if rd_data1 /= rd_data2 then
                        next_pc := std_logic_vector(signed(pc) + signed(rd_data2));
                    end if;
                when BRANCH_TYPE_BLT =>
                    if signed(rd_data1) < signed(rd_data2) then
                        next_pc := std_logic_vector(signed(pc) + signed(rd_data2));
                    end if;
                when BRANCH_TYPE_BGE =>
                    if signed(rd_data1) >= signed(rd_data2) then
                        next_pc := std_logic_vector(signed(pc) + signed(rd_data2));
                    end if;
                when others => null;
            end case;
        end if;

        pc <= next_pc;
    end process;

    -- Writeback logic
    process(clk, rst)
    begin
        if rst = '1' then
            pc <= std_logic_vector(to_unsigned(RESET_HANDLER_ADDRESS, 32));
        elsif rising_edge(clk) then
            case rd_data_source is
                when RD_DATA_SOURCE_PC_IMM =>
                    wr_data <= std_logic_vector(signed(pc) + signed(rd_data2));
                when RD_DATA_SOURCE_PC_4 =>
                    wr_data <= std_logic_vector(unsigned(pc) + 4);
                when RD_DATA_SOURCE_IMM =>
                    wr_data <= rd_data1;  -- Immediate value from instruction
                when RD_DATA_SOURCE_ALU_RESULT =>
                    wr_data <= alu_result;
                when RD_DATA_SOURCE_MEM_DATA_OUT =>
                    wr_data <= mem_data_out;
            end case;

            if wr_en = '1' and wr_addr /= "00000" then  -- x0 should not be written
                register_file_inst.registers(to_integer(unsigned(wr_addr))) <= wr_data;
            end if;
        end if;
    end process;

end Behavioral;
