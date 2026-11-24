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

architecture structural of cpu is
    signal pc               : std_logic_vector(31 downto 0);
    signal pc_plus_4        : std_logic_vector(31 downto 0);
    signal next_pc          : std_logic_vector(31 downto 0);

    signal rs1_data         : std_logic_vector(31 downto 0);
    signal rs2_data         : std_logic_vector(31 downto 0);
    signal register_write   : std_logic;
    signal writeback_data   : std_logic_vector(31 downto 0);

    signal imm_i            : std_logic_vector(31 downto 0);
    signal imm_s            : std_logic_vector(31 downto 0);
    signal imm_b            : std_logic_vector(31 downto 0);
    signal imm_u            : std_logic_vector(31 downto 0);
    signal imm_j            : std_logic_vector(31 downto 0);
    signal mem_write        : std_logic;
    signal mem_width        : std_logic_vector(1 downto 0);
    signal is_load          : std_logic;
    signal load_funct3      : std_logic_vector(2 downto 0);
    signal alu_src_imm      : std_logic;
    signal writeback_sel    : std_logic_vector(1 downto 0);

    signal alu_instr        : std_logic_vector(31 downto 0);
    signal alu_operand_a    : std_logic_vector(31 downto 0);
    signal alu_operand_b    : std_logic_vector(31 downto 0);
    signal alu_result       : std_logic_vector(31 downto 0);
    signal branch_taken     : std_logic;

    signal load_data        : std_logic_vector(31 downto 0);
    signal branch_target    : std_logic_vector(31 downto 0);
    signal jalr_sum         : std_logic_vector(31 downto 0);
    signal jalr_target      : std_logic_vector(31 downto 0);
begin
    instr_addr <= pc;

    pc_plus_4 <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    u_register_file : entity work.register_file
        port map (
            clk       => clk,
            rst       => rst,
            rs1_addr  => instr_data(19 downto 15),
            rs2_addr  => instr_data(24 downto 20),
            rd_addr   => instr_data(11 downto 7),
            rd_data   => writeback_data,
            rd_write  => register_write,
            rs1_data  => rs1_data,
            rs2_data  => rs2_data
        );

    u_control_unit : entity work.control_unit
        port map (
            instr         => instr_data,
            imm_i         => imm_i,
            imm_s         => imm_s,
            imm_b         => imm_b,
            imm_u         => imm_u,
            imm_j         => imm_j,
            reg_write     => register_write,
            mem_write     => mem_write,
            mem_width     => mem_width,
            is_load       => is_load,
            load_funct3   => load_funct3,
            alu_src_imm   => alu_src_imm,
            writeback_sel => writeback_sel
        );

    process(all)
        variable opcode : std_logic_vector(6 downto 0);
    begin
        opcode := instr_data(6 downto 0);

        alu_instr     <= instr_data;
        alu_operand_a <= rs1_data;
        alu_operand_b <= rs2_data;

        case opcode is
            when "0010011" =>
                alu_operand_b <= imm_i;

            when "0000011" =>
                -- Use the ALU's ADD operation for the load effective address.
                alu_instr     <= x"00000033";
                alu_operand_b <= imm_i;

            when "0100011" =>
                -- Use the ALU's ADD operation for the store effective address.
                alu_instr     <= x"00000033";
                alu_operand_b <= imm_s;

            when "0010111" =>
                alu_instr     <= x"00000033";
                alu_operand_a <= pc;
                alu_operand_b <= imm_u;

            when "0110111" =>
                alu_instr     <= x"00000033";
                alu_operand_a <= (others => '0');
                alu_operand_b <= imm_u;

            when "1101111" =>
                alu_instr     <= x"00000033";
                alu_operand_a <= pc;
                alu_operand_b <= imm_j;

            when "1100111" =>
                alu_instr     <= x"00000033";
                alu_operand_b <= imm_i;

            when others =>
                null;
        end case;
    end process;

    u_alu : entity work.alu
        port map (
            instr        => alu_instr,
            operand_a    => alu_operand_a,
            operand_b    => alu_operand_b,
            result       => alu_result,
            branch_taken => branch_taken
        );

    data_addr       <= alu_result;
    data_write      <= mem_write;
    data_width      <= mem_width;
    data_write_data <= rs2_data;

    process(all)
        variable selected_byte : std_logic_vector(7 downto 0);
        variable selected_half : std_logic_vector(15 downto 0);
    begin
        load_data <= (others => '0');
        selected_byte := (others => '0');
        selected_half := (others => '0');

        case alu_result(1 downto 0) is
            when "00" => selected_byte := data_read_data(7 downto 0);
            when "01" => selected_byte := data_read_data(15 downto 8);
            when "10" => selected_byte := data_read_data(23 downto 16);
            when others => selected_byte := data_read_data(31 downto 24);
        end case;

        if alu_result(1) = '0' then
            selected_half := data_read_data(15 downto 0);
        else
            selected_half := data_read_data(31 downto 16);
        end if;

        if is_load = '1' then
            case load_funct3 is
                when "000" =>
                    load_data <= std_logic_vector(resize(signed(selected_byte), 32));
                when "001" =>
                    load_data <= std_logic_vector(resize(signed(selected_half), 32));
                when "010" =>
                    load_data <= data_read_data;
                when "100" =>
                    load_data <= std_logic_vector(resize(unsigned(selected_byte), 32));
                when "101" =>
                    load_data <= std_logic_vector(resize(unsigned(selected_half), 32));
                when others =>
                    load_data <= (others => '0');
            end case;
        end if;
    end process;

    process(all)
    begin
        case instr_data(6 downto 0) is
            when "0000011" =>
                writeback_data <= load_data;
            when "1101111" | "1100111" =>
                writeback_data <= pc_plus_4;
            when "0110111" =>
                writeback_data <= imm_u;
            when others =>
                writeback_data <= alu_result;
        end case;
    end process;

    branch_target <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
    jalr_sum      <= std_logic_vector(unsigned(rs1_data) + unsigned(imm_i));
    jalr_target   <= jalr_sum(31 downto 1) & '0';

    process(all)
        variable opcode : std_logic_vector(6 downto 0);
    begin
        opcode := instr_data(6 downto 0);
        next_pc <= pc_plus_4;

        if opcode = "1101111" then
            next_pc <= alu_result;
        elsif opcode = "1100111" and instr_data(14 downto 12) = "000" then
            next_pc <= jalr_target;
        elsif opcode = "1100011" and branch_taken = '1' then
            next_pc <= branch_target;
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
end structural;
