-- REQ: FR-RV-04, FR-RV-05, FR-RV-06, FR-RV-12/FR-RV-13/FR-RV-14, FR-RV-15, FR-RV-16

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

    signal pc : std_logic_vector(31 downto 0);
    signal instr : std_logic_vector(31 downto 0);
    signal alu_op_type : ALU_OP_TYPE_t;
    signal reg_write_enable : std_logic;
    signal write_register : std_logic_vector(4 downto 0);
    signal read_register1, read_register2 : std_logic_vector(4 downto 0);
    signal data_in : std_logic_vector(31 downto 0);
    signal data_out1, data_out2 : std_logic_vector(31 downto 0);
    signal mem_access_width : MEM_ACCESS_WIDTH_t;
    signal mem_write_enable : std_logic;
    signal pc_next_src : PC_NEXT_SRC_t;
    signal branch_type : BRANCH_TYPE_t;
    signal rd_data_source : RD_DATA_SOURCE_t;
    signal alu_result : std_logic_vector(31 downto 0);
    signal data_mem_addr : std_logic_vector(31 downto 0);
    signal data_mem_data_out : std_logic_vector(31 downto 0);
    signal m_dispatch : std_logic := '0';
    signal next_pc : std_logic_vector(31 downto 0);

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
            addr                => data_mem_addr,
            mem_write_enable    => mem_write_enable,
            access_width        => mem_access_width,
            data_in             => data_out1,
            
            data_out            => data_mem_data_out
        );

    -- Instantiate register file
    register_file : entity work.register_file
        port map (
            clk             => clk,
            rst             => rst,
            reg_write_enable=> reg_write_enable,
            write_register  => write_register,
            read_register1  => read_register1,
            read_register2  => read_register2,
            data_in         => data_in,
            data_out1       => data_out1,
            data_out2       => data_out2
        );

    -- Instantiate ALU
    alu_inst : entity work.alu
        port map (
            op1         => data_out1,
            op2         => data_out2,
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
            branch_type   => branch_type,
            rd_data_source => rd_data_source
        );

    -- M extension handling
    m_dispatch <= '1' when RV32M_ENABLE and is_rv32m_op(alu_op_type) else '0';

    -- Combinational logic for PC update
    process(pc, alu_result, instr, branch_type, data_out1, data_out2)
    begin
        next_pc <= std_logic_vector(unsigned(pc) + x"00000004");

        case pc_next_src is
            when PC_NEXT_SRC_PC_ALU_RES =>
                next_pc <= alu_result;
            when PC_NEXT_SRC_PC_IMM =>
                next_pc <= std_logic_vector(signed(pc) + signed(instr(31 downto 20) & "000"));
            when PC_NEXT_SRC_PC_4 =>
                next_pc <= std_logic_vector(unsigned(pc) + x"00000004");
        end case;

        -- Branch handling
        if branch_type /= BRANCH_TYPE_NONE then
            case branch_type is
                when BRANCH_TYPE_BEQ =>
                    if data_out1 = data_out2 then
                        next_pc <= std_logic_vector(signed(pc) + signed(instr(31 downto 8) & "000"));
                    end if;
                when BRANCH_TYPE_BNE =>
                    if data_out1 /= data_out2 then
                        next_pc <= std_logic_vector(signed(pc) + signed(instr(31 downto 8) & "000"));
                    end if;
                when BRANCH_TYPE_BLT =>
                    if signed(data_out1) < signed(data_out2) then
                        next_pc <= std_logic_vector(signed(pc) + signed(instr(31 downto 8) & "000"));
                    end if;
                when BRANCH_TYPE_BGE =>
                    if signed(data_out1) >= signed(data_out2) then
                        next_pc <= std_logic_vector(signed(pc) + signed(instr(31 downto 8) & "000"));
                    end if;
                when others => null;
            end case;
        end if;
    end process;

    -- Sequential logic for PC update
    process(clk, rst)
    begin
        if rst = '1' then
            pc <= std_logic_vector(to_unsigned(RESET_HANDLER_ADDRESS, 32));
        elsif rising_edge(clk) then
            pc <= next_pc;
        end if;
    end process;

    -- Combinational logic for data memory address
    data_mem_addr <= alu_result when rd_data_source = RD_DATA_SOURCE_ALU_RESULT else std_logic_vector(unsigned(pc) + x"00000004");

    -- Combinational logic for data_in to register file
    process(rd_data_source, alu_result, instr, data_mem_data_out)
    begin
        case rd_data_source is
            when RD_DATA_SOURCE_PC_IMM =>
                data_in <= std_logic_vector(signed(pc) + signed(instr(31 downto 20) & "000"));
            when RD_DATA_SOURCE_PC_4 =>
                data_in <= std_logic_vector(unsigned(pc) + x"00000004");
            when RD_DATA_SOURCE_IMM =>
                data_in <= instr(31 downto 20) & "0000000000000000";
            when RD_DATA_SOURCE_ALU_RESULT =>
                data_in <= alu_result;
            when RD_DATA_SOURCE_MEM_DATA_OUT =>
                case mem_access_width is
                    when MEM_ACCESS_WIDTH_8 =>
                        data_in <= std_logic_vector(resize(signed(data_mem_data_out(7 downto 0)), 32));
                    when MEM_ACCESS_WIDTH_16 =>
                        data_in <= std_logic_vector(resize(signed(data_mem_data_out(15 downto 0)), 32));
                    when MEM_ACCESS_WIDTH_32 =>
                        data_in <= data_mem_data_out;
                end case;
        end case;
    end process;

end Behavioral;
