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

architecture structural of cpu is
    signal pc : std_logic_vector(31 downto 0);
    signal next_pc : std_logic_vector(31 downto 0);
    signal pc_plus_four : std_logic_vector(31 downto 0);

    signal rs1_data : std_logic_vector(31 downto 0);
    signal rs2_data : std_logic_vector(31 downto 0);
    signal rd_data : std_logic_vector(31 downto 0);

    signal imm_i : std_logic_vector(31 downto 0);
    signal imm_s : std_logic_vector(31 downto 0);
    signal imm_b : std_logic_vector(31 downto 0);
    signal imm_u : std_logic_vector(31 downto 0);
    signal imm_j : std_logic_vector(31 downto 0);

    signal reg_write_ctrl : std_logic;
    signal mem_write_ctrl : std_logic;
    signal data_width_ctrl : std_logic_vector(1 downto 0);
    signal alu_src_a_pc : std_logic;
    signal alu_src_b_imm : std_logic;
    signal alu_op : std_logic_vector(4 downto 0);
    signal wb_sel : std_logic_vector(1 downto 0);
    signal imm_sel : std_logic_vector(2 downto 0);
    signal branch : std_logic;
    signal jal : std_logic;
    signal jalr : std_logic;

    signal alu_operand_a : std_logic_vector(31 downto 0);
    signal alu_operand_b : std_logic_vector(31 downto 0);
    signal selected_imm : std_logic_vector(31 downto 0);
    signal alu_result : std_logic_vector(31 downto 0);
    signal alu_equal : std_logic;
    signal alu_signed_less : std_logic;
    signal alu_unsigned_less : std_logic;

    signal jalr_target : std_logic_vector(31 downto 0);
    signal branch_taken : std_logic;
    signal load_value : std_logic_vector(31 downto 0);
begin
    instr_addr <= pc;
    pc_plus_four <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    u_register_file : entity work.register_file
        port map (
            clk => clk,
            rst => rst,
            rs1_addr => instr_data(19 downto 15),
            rs2_addr => instr_data(24 downto 20),
            rd_addr => instr_data(11 downto 7),
            rd_data => rd_data,
            rd_write => reg_write_ctrl,
            rs1_data => rs1_data,
            rs2_data => rs2_data
        );

    u_immediate_generator : entity work.immediate_generator
        port map (
            instr => instr_data,
            imm_i => imm_i,
            imm_s => imm_s,
            imm_b => imm_b,
            imm_u => imm_u,
            imm_j => imm_j
        );

    u_control_unit : entity work.control_unit
        port map (
            instr => instr_data,
            reg_write => reg_write_ctrl,
            mem_write => mem_write_ctrl,
            data_width => data_width_ctrl,
            alu_src_a_pc => alu_src_a_pc,
            alu_src_b_imm => alu_src_b_imm,
            alu_op => alu_op,
            wb_sel => wb_sel,
            imm_sel => imm_sel,
            branch => branch,
            jal => jal,
            jalr => jalr
        );

    u_alu : entity work.alu
        port map (
            operand_a => alu_operand_a,
            operand_b => alu_operand_b,
            alu_op => alu_op,
            result => alu_result,
            equal => alu_equal,
            signed_less => alu_signed_less,
            unsigned_less => alu_unsigned_less
        );

    process(all)
    begin
        selected_imm <= (others => '0');
        case imm_sel is
            when "001" =>
                selected_imm <= imm_i;
            when "010" =>
                selected_imm <= imm_s;
            when "011" =>
                selected_imm <= imm_b;
            when "100" =>
                selected_imm <= imm_u;
            when "101" =>
                selected_imm <= imm_j;
            when others =>
                selected_imm <= (others => '0');
        end case;
    end process;

    alu_operand_a <= pc when alu_src_a_pc = '1' else rs1_data;
    alu_operand_b <= selected_imm when alu_src_b_imm = '1' else rs2_data;

    jalr_target <= alu_result(31 downto 1) & '0';
    branch_taken <= alu_result(0);

    process(all)
    begin
        next_pc <= pc_plus_four;
        if jal = '1' then
            next_pc <= alu_result;
        elsif jalr = '1' then
            next_pc <= jalr_target;
        elsif branch = '1' and branch_taken = '1' then
            next_pc <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
        end if;
    end process;

    process(clk, rst)
    begin
        if rst = '1' then
            pc <= (others => '0');
        elsif rising_edge(clk) then
            pc <= next_pc;
        end if;
    end process;

    process(all)
        variable byte_value : std_logic_vector(7 downto 0);
        variable half_value : std_logic_vector(15 downto 0);
    begin
        byte_value := (others => '0');
        half_value := (others => '0');
        load_value <= data_read_data;

        case instr_data(14 downto 12) is
            when "000" | "100" =>
                case alu_result(1 downto 0) is
                    when "00" => byte_value := data_read_data(7 downto 0);
                    when "01" => byte_value := data_read_data(15 downto 8);
                    when "10" => byte_value := data_read_data(23 downto 16);
                    when others => byte_value := data_read_data(31 downto 24);
                end case;
                if instr_data(14 downto 12) = "000" then
                    load_value <= std_logic_vector(resize(signed(byte_value), 32));
                else
                    load_value <= std_logic_vector(resize(unsigned(byte_value), 32));
                end if;

            when "001" | "101" =>
                if alu_result(1) = '0' then
                    half_value := data_read_data(15 downto 0);
                else
                    half_value := data_read_data(31 downto 16);
                end if;
                if instr_data(14 downto 12) = "001" then
                    load_value <= std_logic_vector(resize(signed(half_value), 32));
                else
                    load_value <= std_logic_vector(resize(unsigned(half_value), 32));
                end if;

            when "010" =>
                load_value <= data_read_data;

            when others =>
                load_value <= data_read_data;
        end case;
    end process;

    process(all)
    begin
        rd_data <= alu_result;
        case wb_sel is
            when "01" =>
                rd_data <= load_value;
            when "10" =>
                rd_data <= pc_plus_four;
            when others =>
                rd_data <= alu_result;
        end case;
    end process;

    data_width <= data_width_ctrl;
    data_write <= '1' when mem_write_ctrl = '1' and rst = '0' else '0';
    data_write_data <= rs2_data;

    process(all)
    begin
        data_addr <= (others => '0');
        if mem_write_ctrl = '1' or wb_sel = "01" then
            data_addr <= alu_result;
        end if;
    end process;
end structural;
