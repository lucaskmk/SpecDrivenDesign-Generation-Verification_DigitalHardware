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
end entity cpu;

architecture rtl of cpu is
    signal pc : std_logic_vector(31 downto 0);
    signal pc_plus4 : std_logic_vector(31 downto 0);
    signal next_pc : std_logic_vector(31 downto 0);

    signal imm_i : std_logic_vector(31 downto 0);
    signal imm_s : std_logic_vector(31 downto 0);
    signal imm_b : std_logic_vector(31 downto 0);
    signal imm_u : std_logic_vector(31 downto 0);
    signal imm_j : std_logic_vector(31 downto 0);

    signal rs1_data : std_logic_vector(31 downto 0);
    signal rs2_data : std_logic_vector(31 downto 0);
    signal rd_data : std_logic_vector(31 downto 0);
    signal rd_write : std_logic;

    signal reg_write_dec : std_logic;
    signal mem_write_dec : std_logic;
    signal alu_src_a_pc : std_logic;
    signal alu_src_b_imm : std_logic;
    signal decoder_alu_control : std_logic_vector(3 downto 0);
    signal branch_enable : std_logic;
    signal jump : std_logic;
    signal jalr : std_logic;
    signal wb_select : std_logic_vector(1 downto 0);

    signal alu_operand_a : std_logic_vector(31 downto 0);
    signal alu_operand_b : std_logic_vector(31 downto 0);
    signal alu_control : std_logic_vector(3 downto 0);
    signal alu_result : std_logic_vector(31 downto 0);
    signal alu_equal : std_logic;
    signal alu_signed_less : std_logic;
    signal alu_unsigned_less : std_logic;

    signal branch_taken : std_logic;
    signal jump_target : std_logic_vector(31 downto 0);
    signal effective_addr : std_logic_vector(31 downto 0);
    signal load_value : std_logic_vector(31 downto 0);
    signal mem_write_enable : std_logic;
begin
    u_immediate_generator : entity work.immediate_generator
        port map (
            instr => instr_data,
            imm_i => imm_i,
            imm_s => imm_s,
            imm_b => imm_b,
            imm_u => imm_u,
            imm_j => imm_j
        );

    u_register_file : entity work.register_file
        port map (
            clk => clk,
            rst => rst,
            rs1_addr => instr_data(19 downto 15),
            rs2_addr => instr_data(24 downto 20),
            rs1_data => rs1_data,
            rs2_data => rs2_data,
            rd_addr => instr_data(11 downto 7),
            rd_data => rd_data,
            rd_write => rd_write
        );

    u_alu : entity work.alu
        port map (
            operand_a => alu_operand_a,
            operand_b => alu_operand_b,
            alu_control => alu_control,
            result => alu_result,
            equal => alu_equal,
            signed_less => alu_signed_less,
            unsigned_less => alu_unsigned_less
        );

    u_decoder : entity work.decoder
        port map (
            instr => instr_data,
            reg_write => reg_write_dec,
            mem_write => mem_write_dec,
            alu_src_a_pc => alu_src_a_pc,
            alu_src_b_imm => alu_src_b_imm,
            alu_control => decoder_alu_control,
            branch_enable => branch_enable,
            jump => jump,
            jalr => jalr,
            wb_select => wb_select
        );

    instr_addr <= (others => '0') when rst = '1' else pc;
    pc_plus4 <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    process(all)
    begin
        alu_operand_a <= rs1_data;
        if alu_src_a_pc = '1' then
            alu_operand_a <= pc;
        end if;

        alu_operand_b <= rs2_data;
        if alu_src_b_imm = '1' then
            case instr_data(6 downto 0) is
                when "0100011" =>
                    alu_operand_b <= imm_s;
                when "0110111" | "0010111" =>
                    alu_operand_b <= imm_u;
                when others =>
                    alu_operand_b <= imm_i;
            end case;
        end if;

        alu_control <= "0000";
        if branch_enable = '0' and instr_data(6 downto 0) /= "0110111" then
            case decoder_alu_control is
                when "0000" => alu_control <= "0000";
                when "0001" => alu_control <= "0001";
                when "0010" => alu_control <= "0101";
                when "0011" => alu_control <= "1000";
                when "0100" => alu_control <= "1001";
                when "0101" => alu_control <= "0100";
                when "0110" => alu_control <= "0110";
                when "0111" => alu_control <= "0111";
                when "1000" => alu_control <= "0011";
                when "1001" => alu_control <= "0010";
                when others => alu_control <= "0000";
            end case;
        end if;
    end process;

    process(all)
    begin
        branch_taken <= '0';
        if branch_enable = '1' then
            case decoder_alu_control is
                when "0000" =>
                    branch_taken <= alu_equal;
                when "0001" =>
                    branch_taken <= not alu_equal;
                when "0010" =>
                    branch_taken <= alu_signed_less;
                when "0011" =>
                    branch_taken <= not alu_signed_less;
                when "0100" =>
                    branch_taken <= alu_unsigned_less;
                when "0101" =>
                    branch_taken <= not alu_unsigned_less;
                when others =>
                    branch_taken <= '0';
            end case;
        end if;
    end process;

    process(all)
        variable target_value : std_logic_vector(31 downto 0);
    begin
        if jalr = '1' then
            target_value := std_logic_vector(unsigned(rs1_data) + unsigned(imm_i));
            target_value(0) := '0';
            jump_target <= target_value;
        else
            jump_target <= std_logic_vector(unsigned(pc) + unsigned(imm_j));
        end if;
    end process;

    process(all)
    begin
        next_pc <= pc_plus4;
        if jump = '1' then
            if jalr = '1' then
                next_pc <= jump_target;
            else
                next_pc <= std_logic_vector(unsigned(pc) + unsigned(imm_j));
            end if;
        elsif branch_taken = '1' then
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

    effective_addr <= alu_result;
    data_addr <= effective_addr;
    data_write_data <= rs2_data;
    mem_write_enable <= mem_write_dec when rst = '0' else '0';
    data_write <= mem_write_enable;

    process(all)
    begin
        data_width <= "10";
        case instr_data(6 downto 0) is
            when "0000011" | "0100011" =>
                case instr_data(14 downto 12) is
                    when "000" | "100" =>
                        data_width <= "00";
                    when "001" | "101" =>
                        data_width <= "01";
                    when "010" =>
                        data_width <= "10";
                    when others =>
                        data_width <= "10";
                end case;
            when others =>
                data_width <= "10";
        end case;
    end process;

    process(all)
        variable selected_byte : std_logic_vector(7 downto 0);
        variable selected_half : std_logic_vector(15 downto 0);
    begin
        selected_byte := data_read_data(7 downto 0);
        selected_half := data_read_data(15 downto 0);

        case effective_addr(1 downto 0) is
            when "00" =>
                selected_byte := data_read_data(7 downto 0);
                selected_half := data_read_data(15 downto 0);
            when "01" =>
                selected_byte := data_read_data(15 downto 8);
                selected_half := data_read_data(15 downto 0);
            when "10" =>
                selected_byte := data_read_data(23 downto 16);
                selected_half := data_read_data(31 downto 16);
            when others =>
                selected_byte := data_read_data(31 downto 24);
                selected_half := data_read_data(31 downto 16);
        end case;

        load_value <= data_read_data;
        case instr_data(14 downto 12) is
            when "000" =>
                load_value <= std_logic_vector(resize(signed(selected_byte), 32));
            when "001" =>
                load_value <= std_logic_vector(resize(signed(selected_half), 32));
            when "010" =>
                load_value <= data_read_data;
            when "100" =>
                load_value <= std_logic_vector(resize(unsigned(selected_byte), 32));
            when "101" =>
                load_value <= std_logic_vector(resize(unsigned(selected_half), 32));
            when others =>
                load_value <= data_read_data;
        end case;
    end process;

    process(all)
    begin
        rd_data <= alu_result;
        case wb_select is
            when "00" =>
                if instr_data(6 downto 0) = "0110111" then
                    rd_data <= imm_u;
                else
                    rd_data <= alu_result;
                end if;
            when "01" =>
                rd_data <= load_value;
            when "10" =>
                rd_data <= pc_plus4;
            when others =>
                rd_data <= (others => '0');
        end case;
    end process;

    rd_write <= reg_write_dec when rst = '0' else '0';
end architecture rtl;
