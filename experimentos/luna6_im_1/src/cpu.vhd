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
    signal pc : std_logic_vector(31 downto 0);
    signal pc_plus_4 : std_logic_vector(31 downto 0);
    signal next_pc : std_logic_vector(31 downto 0);

    signal opcode : std_logic_vector(6 downto 0);
    signal funct3 : std_logic_vector(2 downto 0);
    signal funct7 : std_logic_vector(6 downto 0);
    signal rd : std_logic_vector(4 downto 0);
    signal rs1 : std_logic_vector(4 downto 0);
    signal rs2 : std_logic_vector(4 downto 0);

    signal read_data1 : std_logic_vector(31 downto 0);
    signal read_data2 : std_logic_vector(31 downto 0);
    signal imm_i : std_logic_vector(31 downto 0);
    signal imm_s : std_logic_vector(31 downto 0);
    signal imm_b : std_logic_vector(31 downto 0);
    signal imm_u : std_logic_vector(31 downto 0);
    signal imm_j : std_logic_vector(31 downto 0);

    signal alu_operand_b : std_logic_vector(31 downto 0);
    signal alu_result : std_logic_vector(31 downto 0);
    signal branch_taken : std_logic;

    signal effective_address : std_logic_vector(31 downto 0);
    signal lsu_data_write : std_logic;
    signal lsu_data_write_data : std_logic_vector(31 downto 0);
    signal load_result : std_logic_vector(31 downto 0);

    signal reg_write_enable : std_logic;
    signal reg_write_data : std_logic_vector(31 downto 0);
    signal jalr_valid : std_logic;
    signal branch_valid : std_logic;
    signal op_valid : std_logic;
    signal op_imm_valid : std_logic;
    signal load_valid : std_logic;

    function supported_op(f3 : std_logic_vector(2 downto 0);
                          f7 : std_logic_vector(6 downto 0))
        return boolean is
    begin
        case f7 is
            when "0000000" =>
                return true;
            when "0100000" =>
                return f3 = "000" or f3 = "101";
            when "0000001" =>
                return true;
            when others =>
                return false;
        end case;
    end function;

    function supported_op_imm(f3 : std_logic_vector(2 downto 0);
                              f7 : std_logic_vector(6 downto 0))
        return boolean is
    begin
        case f3 is
            when "000" | "010" | "011" | "100" | "110" | "111" =>
                return true;
            when "001" =>
                return f7 = "0000000";
            when "101" =>
                return f7 = "0000000" or f7 = "0100000";
            when others =>
                return false;
        end case;
    end function;
begin
    opcode <= instr_data(6 downto 0);
    rd <= instr_data(11 downto 7);
    funct3 <= instr_data(14 downto 12);
    rs1 <= instr_data(19 downto 15);
    rs2 <= instr_data(24 downto 20);
    funct7 <= instr_data(31 downto 25);

    instr_addr <= pc;
    pc_plus_4 <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    u_register_file : entity work.register_file
        port map(
            clk => clk,
            rst => rst,
            read_addr1 => rs1,
            read_addr2 => rs2,
            read_data1 => read_data1,
            read_data2 => read_data2,
            write_enable => reg_write_enable,
            write_addr => rd,
            write_data => reg_write_data
        );

    u_immediate_generator : entity work.immediate_generator
        port map(
            instr => instr_data,
            imm_i => imm_i,
            imm_s => imm_s,
            imm_b => imm_b,
            imm_u => imm_u,
            imm_j => imm_j
        );

    alu_operand_b <= imm_i when opcode = "0010011" else
                     read_data2;

    u_execution_unit : entity work.execution_unit
        port map(
            opcode => opcode,
            funct3 => funct3,
            funct7 => funct7,
            operand_a => read_data1,
            operand_b => alu_operand_b,
            result => alu_result,
            branch_taken => branch_taken
        );

    effective_address <= std_logic_vector(unsigned(read_data1) +
                           unsigned(imm_s))
                         when opcode = "0100011" else
                         std_logic_vector(unsigned(read_data1) +
                           unsigned(imm_i));

    u_load_store_unit : entity work.load_store_unit
        port map(
            instr => instr_data,
            effective_address => effective_address,
            store_data_in => read_data2,
            data_read_data => data_read_data,
            data_addr => data_addr,
            data_write => lsu_data_write,
            data_width => data_width,
            data_write_data => lsu_data_write_data,
            load_result => load_result
        );

    jalr_valid <= '1' when opcode = "1100111" and funct3 = "000" else '0';
    branch_valid <= '1' when opcode = "1100011" and
        (funct3 = "000" or funct3 = "001" or funct3 = "100" or
         funct3 = "101" or funct3 = "110" or funct3 = "111") else '0';
    load_valid <= '1' when opcode = "0000011" and
        (funct3 = "000" or funct3 = "001" or funct3 = "010" or
         funct3 = "100" or funct3 = "101") else '0';
    op_valid <= '1' when opcode = "0110011" and
        supported_op(funct3, funct7) else '0';
    op_imm_valid <= '1' when opcode = "0010011" and
        supported_op_imm(funct3, funct7) else '0';

    process(all)
        variable jalr_target : std_logic_vector(31 downto 0);
    begin
        next_pc <= pc_plus_4;
        jalr_target := std_logic_vector(unsigned(read_data1) + unsigned(imm_i));
        jalr_target(0) := '0';

        if rst = '0' then
            if opcode = "1101111" then
                next_pc <= std_logic_vector(unsigned(pc) + unsigned(imm_j));
            elsif jalr_valid = '1' then
                next_pc <= jalr_target;
            elsif branch_valid = '1' and branch_taken = '1' then
                next_pc <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
            end if;
        end if;
    end process;

    process(all)
    begin
        reg_write_enable <= '0';
        reg_write_data <= (others => '0');

        if rst = '0' then
            if opcode = "0110111" then
                reg_write_enable <= '1';
                reg_write_data <= imm_u;
            elsif opcode = "0010111" then
                reg_write_enable <= '1';
                reg_write_data <= std_logic_vector(unsigned(pc) + unsigned(imm_u));
            elsif opcode = "1101111" then
                reg_write_enable <= '1';
                reg_write_data <= pc_plus_4;
            elsif jalr_valid = '1' then
                reg_write_enable <= '1';
                reg_write_data <= pc_plus_4;
            elsif load_valid = '1' then
                reg_write_enable <= '1';
                reg_write_data <= load_result;
            elsif op_valid = '1' or op_imm_valid = '1' then
                reg_write_enable <= '1';
                reg_write_data <= alu_result;
            end if;
        end if;
    end process;

    data_write <= lsu_data_write when rst = '0' else '0';
    data_write_data <= lsu_data_write_data;

    process(clk, rst)
    begin
        if rst = '1' then
            pc <= (others => '0');
        elsif rising_edge(clk) then
            pc <= next_pc;
        end if;
    end process;
end rtl;
