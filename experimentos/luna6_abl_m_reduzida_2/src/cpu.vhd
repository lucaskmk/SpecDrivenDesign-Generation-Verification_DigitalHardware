library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity cpu is
    port(
        clk             : in  std_logic;
        rst             : in  std_logic;
        instr_addr      : out std_logic_vector(31 downto 0);
        instr_data      : in  std_logic_vector(31 downto 0);
        data_addr       : out std_logic_vector(31 downto 0);
        data_write      : out std_logic;
        data_width      : out std_logic_vector(1 downto 0);
        data_write_data : out std_logic_vector(31 downto 0);
        data_read_data  : in  std_logic_vector(31 downto 0)
    );
end cpu;

architecture rtl of cpu is
    signal pc              : std_logic_vector(31 downto 0);
    signal pc_plus4        : std_logic_vector(31 downto 0);
    signal pc_next         : std_logic_vector(31 downto 0);

    signal opcode          : std_logic_vector(6 downto 0);
    signal funct3          : std_logic_vector(2 downto 0);
    signal funct7          : std_logic_vector(6 downto 0);
    signal rd_addr         : std_logic_vector(4 downto 0);
    signal rs1_data        : std_logic_vector(31 downto 0);
    signal rs2_data        : std_logic_vector(31 downto 0);

    signal imm_i           : std_logic_vector(31 downto 0);
    signal imm_s           : std_logic_vector(31 downto 0);
    signal imm_b           : std_logic_vector(31 downto 0);
    signal imm_u           : std_logic_vector(31 downto 0);
    signal imm_j           : std_logic_vector(31 downto 0);

    signal rd_write        : std_logic;
    signal mem_write       : std_logic;
    signal load_enable     : std_logic;
    signal control_width   : std_logic_vector(1 downto 0);
    signal load_signed     : std_logic;
    signal alu_a_pc        : std_logic;
    signal alu_b_imm       : std_logic;
    signal wb_sel          : std_logic_vector(1 downto 0);
    signal branch_enable   : std_logic;
    signal jal             : std_logic;
    signal jalr            : std_logic;

    signal alu_operand_a   : std_logic_vector(31 downto 0);
    signal alu_operand_b   : std_logic_vector(31 downto 0);
    signal alu_opcode      : std_logic_vector(6 downto 0);
    signal alu_funct3      : std_logic_vector(2 downto 0);
    signal alu_funct7      : std_logic_vector(6 downto 0);
    signal alu_result      : std_logic_vector(31 downto 0);

    signal branch_taken    : std_logic;
    signal load_value      : std_logic_vector(31 downto 0);
    signal writeback_data  : std_logic_vector(31 downto 0);
begin
    opcode  <= instr_data(6 downto 0);
    rd_addr <= instr_data(11 downto 7);
    funct3  <= instr_data(14 downto 12);
    funct7  <= instr_data(31 downto 25);

    instr_addr      <= pc;
    data_addr       <= alu_result;
    data_write      <= mem_write;
    data_width      <= control_width;
    data_write_data <= rs2_data;

    pc_plus4 <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    u_immediate_gen : entity work.immediate_gen
        port map (
            instr  => instr_data,
            imm_i  => imm_i,
            imm_s  => imm_s,
            imm_b  => imm_b,
            imm_u  => imm_u,
            imm_j  => imm_j
        );

    u_register_file : entity work.register_file
        port map (
            clk      => clk,
            rst      => rst,
            rs1_addr => instr_data(19 downto 15),
            rs2_addr => instr_data(24 downto 20),
            rd_addr  => rd_addr,
            rd_data  => writeback_data,
            rd_write => rd_write,
            rs1_data => rs1_data,
            rs2_data => rs2_data
        );

    u_control_unit : entity work.control_unit
        port map (
            opcode        => opcode,
            funct3        => funct3,
            rd_write      => rd_write,
            mem_write     => mem_write,
            load_enable   => load_enable,
            data_width    => control_width,
            load_signed   => load_signed,
            alu_a_pc      => alu_a_pc,
            alu_b_imm     => alu_b_imm,
            wb_sel        => wb_sel,
            branch_enable => branch_enable,
            jal           => jal,
            jalr          => jalr
        );

    process(all)
    begin
        if alu_a_pc = '1' then
            alu_operand_a <= pc;
        else
            alu_operand_a <= rs1_data;
        end if;

        if alu_b_imm = '1' then
            alu_operand_b <= imm_i;
        else
            alu_operand_b <= rs2_data;
        end if;

        alu_opcode <= opcode;
        alu_funct3 <= funct3;
        alu_funct7 <= funct7;

        case opcode is
            when "0110111" => -- LUI
                alu_operand_a <= (others => '0');
                alu_operand_b <= imm_u;
                alu_opcode    <= "0010011";
                alu_funct3    <= "000";
                alu_funct7    <= (others => '0');

            when "0010111" => -- AUIPC
                alu_operand_b <= imm_u;
                alu_opcode    <= "0010011";
                alu_funct3    <= "000";
                alu_funct7    <= (others => '0');

            when "0000011" => -- Loads
                alu_operand_a <= rs1_data;
                alu_operand_b <= imm_i;
                alu_opcode    <= "0010011";
                alu_funct3    <= "000";
                alu_funct7    <= (others => '0');

            when "0100011" => -- Stores
                alu_operand_a <= rs1_data;
                alu_operand_b <= imm_s;
                alu_opcode    <= "0010011";
                alu_funct3    <= "000";
                alu_funct7    <= (others => '0');

            when "1100011" => -- Branch comparisons
                alu_operand_a <= rs1_data;
                alu_operand_b <= rs2_data;
                alu_opcode    <= "0110011";
                alu_funct7    <= (others => '0');
                case funct3 is
                    when "000" | "001" =>
                        alu_funct3 <= "000";
                        alu_funct7 <= "0100000";
                    when "100" | "101" =>
                        alu_funct3 <= "010";
                    when "110" | "111" =>
                        alu_funct3 <= "011";
                    when others =>
                        alu_funct3 <= "000";
                end case;

            when "1101111" => -- JAL
                alu_operand_a <= pc;
                alu_operand_b <= imm_j;
                alu_opcode    <= "0010011";
                alu_funct3    <= "000";
                alu_funct7    <= (others => '0');

            when "1100111" => -- JALR
                alu_operand_a <= rs1_data;
                alu_operand_b <= imm_i;
                alu_opcode    <= "0010011";
                alu_funct3    <= "000";
                alu_funct7    <= (others => '0');

            when others =>
                null;
        end case;
    end process;

    u_alu : entity work.alu
        port map (
            operand_a => alu_operand_a,
            operand_b => alu_operand_b,
            opcode    => alu_opcode,
            funct3    => alu_funct3,
            funct7    => alu_funct7,
            result    => alu_result
        );

    process(all)
        variable byte_value : std_logic_vector(7 downto 0);
        variable half_value : std_logic_vector(15 downto 0);
    begin
        byte_value := (others => '0');
        half_value := (others => '0');

        case alu_result(1 downto 0) is
            when "00" => byte_value := data_read_data(7 downto 0);
            when "01" => byte_value := data_read_data(15 downto 8);
            when "10" => byte_value := data_read_data(23 downto 16);
            when others => byte_value := data_read_data(31 downto 24);
        end case;

        if alu_result(1) = '1' then
            half_value := data_read_data(31 downto 16);
        else
            half_value := data_read_data(15 downto 0);
        end if;

        load_value <= data_read_data;
        if load_enable = '1' then
            case control_width is
                when "00" =>
                    if load_signed = '1' then
                        load_value <= std_logic_vector(resize(signed(byte_value), 32));
                    else
                        load_value <= std_logic_vector(resize(unsigned(byte_value), 32));
                    end if;
                when "01" =>
                    if load_signed = '1' then
                        load_value <= std_logic_vector(resize(signed(half_value), 32));
                    else
                        load_value <= std_logic_vector(resize(unsigned(half_value), 32));
                    end if;
                when others =>
                    load_value <= data_read_data;
            end case;
        end if;
    end process;

    process(all)
    begin
        branch_taken <= '0';

        if branch_enable = '1' then
            case funct3 is
                when "000" =>
                    if alu_result = x"00000000" then
                        branch_taken <= '1';
                    end if;
                when "001" =>
                    if alu_result /= x"00000000" then
                        branch_taken <= '1';
                    end if;
                when "100" | "110" =>
                    if alu_result(0) = '1' then
                        branch_taken <= '1';
                    end if;
                when "101" | "111" =>
                    if alu_result(0) = '0' then
                        branch_taken <= '1';
                    end if;
                when others =>
                    branch_taken <= '0';
            end case;
        end if;
    end process;

    process(all)
        variable jalr_target : std_logic_vector(31 downto 0);
    begin
        pc_next <= pc_plus4;

        if jal = '1' then
            pc_next <= std_logic_vector(unsigned(pc) + unsigned(imm_j));
        elsif jalr = '1' then
            jalr_target := alu_result;
            jalr_target(0) := '0';
            pc_next <= jalr_target;
        elsif branch_taken = '1' then
            pc_next <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
        end if;
    end process;

    process(all)
    begin
        case wb_sel is
            when "00" =>
                writeback_data <= alu_result;
            when "01" =>
                writeback_data <= load_value;
            when "10" =>
                writeback_data <= pc_plus4;
            when others =>
                writeback_data <= (others => '0');
        end case;
    end process;

    process(clk, rst)
    begin
        if rst = '1' then
            pc <= (others => '0');
        elsif rising_edge(clk) then
            pc <= pc_next;
        end if;
    end process;
end rtl;
