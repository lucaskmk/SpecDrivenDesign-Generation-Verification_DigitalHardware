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
    signal pc_plus4 : std_logic_vector(31 downto 0);
    signal next_pc : std_logic_vector(31 downto 0);

    signal opcode : std_logic_vector(6 downto 0);
    signal rd : std_logic_vector(4 downto 0);
    signal funct3 : std_logic_vector(2 downto 0);
    signal rs1 : std_logic_vector(4 downto 0);
    signal rs2 : std_logic_vector(4 downto 0);
    signal funct7 : std_logic_vector(6 downto 0);

    signal rs1_data : std_logic_vector(31 downto 0);
    signal rs2_data : std_logic_vector(31 downto 0);
    signal reg_write_enable : std_logic;
    signal reg_write_data : std_logic_vector(31 downto 0);

    signal imm_i : std_logic_vector(31 downto 0);
    signal imm_s : std_logic_vector(31 downto 0);
    signal imm_b : std_logic_vector(31 downto 0);
    signal imm_u : std_logic_vector(31 downto 0);
    signal imm_j : std_logic_vector(31 downto 0);

    signal alu_operand_b : std_logic_vector(31 downto 0);
    signal alu_result : std_logic_vector(31 downto 0);

    signal load_addr : std_logic_vector(31 downto 0);
    signal store_addr : std_logic_vector(31 downto 0);
begin
    opcode <= instr_data(6 downto 0);
    rd <= instr_data(11 downto 7);
    funct3 <= instr_data(14 downto 12);
    rs1 <= instr_data(19 downto 15);
    rs2 <= instr_data(24 downto 20);
    funct7 <= instr_data(31 downto 25);

    instr_addr <= pc;
    pc_plus4 <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    load_addr <= std_logic_vector(unsigned(rs1_data) + unsigned(imm_i));
    store_addr <= std_logic_vector(unsigned(rs1_data) + unsigned(imm_s));

    alu_operand_b <= imm_i when opcode = "0010011" else rs2_data;

    u_register_file : entity work.register_file
        port map(
            clk => clk,
            rst => rst,
            read_addr1 => rs1,
            read_addr2 => rs2,
            read_data1 => rs1_data,
            read_data2 => rs2_data,
            write_enable => reg_write_enable,
            write_addr => rd,
            write_data => reg_write_data
        );

    u_immediate_decoder : entity work.immediate_decoder
        port map(
            instr => instr_data,
            imm_i => imm_i,
            imm_s => imm_s,
            imm_b => imm_b,
            imm_u => imm_u,
            imm_j => imm_j
        );

    u_rv32im_alu : entity work.rv32im_alu
        port map(
            opcode => opcode,
            funct3 => funct3,
            funct7 => funct7,
            operand_a => rs1_data,
            operand_b => alu_operand_b,
            result => alu_result
        );

    process(all)
        variable branch_condition : boolean;
        variable jalr_target : std_logic_vector(31 downto 0);
        variable selected_byte : std_logic_vector(7 downto 0);
        variable selected_half : std_logic_vector(15 downto 0);
    begin
        next_pc <= pc_plus4;
        reg_write_enable <= '0';
        reg_write_data <= (others => '0');

        data_addr <= (others => '0');
        data_write <= '0';
        data_width <= "10";
        data_write_data <= (others => '0');

        branch_condition := false;
        jalr_target := (others => '0');
        selected_byte := (others => '0');
        selected_half := (others => '0');

        if rst = '0' then
            case opcode is
                when "0110111" =>
                    reg_write_enable <= '1';
                    reg_write_data <= imm_u;

                when "0010111" =>
                    reg_write_enable <= '1';
                    reg_write_data <= std_logic_vector(unsigned(pc) + unsigned(imm_u));

                when "1101111" =>
                    reg_write_enable <= '1';
                    reg_write_data <= pc_plus4;
                    next_pc <= std_logic_vector(unsigned(pc) + unsigned(imm_j));

                when "1100111" =>
                    if funct3 = "000" then
                        reg_write_enable <= '1';
                        reg_write_data <= pc_plus4;
                        jalr_target := std_logic_vector(unsigned(rs1_data) + unsigned(imm_i));
                        jalr_target(0) := '0';
                        next_pc <= jalr_target;
                    end if;

                when "1100011" =>
                    case funct3 is
                        when "000" =>
                            branch_condition := rs1_data = rs2_data;
                        when "001" =>
                            branch_condition := rs1_data /= rs2_data;
                        when "100" =>
                            branch_condition := signed(rs1_data) < signed(rs2_data);
                        when "101" =>
                            branch_condition := signed(rs1_data) >= signed(rs2_data);
                        when "110" =>
                            branch_condition := unsigned(rs1_data) < unsigned(rs2_data);
                        when "111" =>
                            branch_condition := unsigned(rs1_data) >= unsigned(rs2_data);
                        when others =>
                            branch_condition := false;
                    end case;

                    if branch_condition then
                        next_pc <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
                    end if;

                when "0000011" =>
                    case funct3 is
                        when "000" | "001" | "010" | "100" | "101" =>
                            data_addr <= load_addr;
                            reg_write_enable <= '1';

                            case load_addr(1 downto 0) is
                                when "00" => selected_byte := data_read_data(7 downto 0);
                                when "01" => selected_byte := data_read_data(15 downto 8);
                                when "10" => selected_byte := data_read_data(23 downto 16);
                                when others => selected_byte := data_read_data(31 downto 24);
                            end case;

                            if load_addr(1) = '0' then
                                selected_half := data_read_data(15 downto 0);
                            else
                                selected_half := data_read_data(31 downto 16);
                            end if;

                            case funct3 is
                                when "000" =>
                                    reg_write_data <= std_logic_vector(resize(signed(selected_byte), 32));
                                when "001" =>
                                    reg_write_data <= std_logic_vector(resize(signed(selected_half), 32));
                                when "010" =>
                                    reg_write_data <= data_read_data;
                                when "100" =>
                                    reg_write_data <= std_logic_vector(resize(unsigned(selected_byte), 32));
                                when "101" =>
                                    reg_write_data <= std_logic_vector(resize(unsigned(selected_half), 32));
                                when others =>
                                    null;
                            end case;
                        when others =>
                            null;
                    end case;

                when "0100011" =>
                    case funct3 is
                        when "000" =>
                            data_addr <= store_addr;
                            data_write <= '1';
                            data_width <= "00";
                            data_write_data <= rs2_data;
                        when "001" =>
                            data_addr <= store_addr;
                            data_write <= '1';
                            data_width <= "01";
                            data_write_data <= rs2_data;
                        when "010" =>
                            data_addr <= store_addr;
                            data_write <= '1';
                            data_width <= "10";
                            data_write_data <= rs2_data;
                        when others =>
                            null;
                    end case;

                when "0010011" =>
                    case funct3 is
                        when "000" | "010" | "011" | "100" | "110" | "111" =>
                            reg_write_enable <= '1';
                            reg_write_data <= alu_result;
                        when "001" =>
                            if funct7 = "0000000" then
                                reg_write_enable <= '1';
                                reg_write_data <= alu_result;
                            end if;
                        when "101" =>
                            if funct7 = "0000000" or funct7 = "0100000" then
                                reg_write_enable <= '1';
                                reg_write_data <= alu_result;
                            end if;
                        when others =>
                            null;
                    end case;

                when "0110011" =>
                    case funct7 is
                        when "0000000" =>
                            reg_write_enable <= '1';
                            reg_write_data <= alu_result;
                        when "0100000" =>
                            if funct3 = "000" or funct3 = "101" then
                                reg_write_enable <= '1';
                                reg_write_data <= alu_result;
                            end if;
                        when "0000001" =>
                            reg_write_enable <= '1';
                            reg_write_data <= alu_result;
                        when others =>
                            null;
                    end case;

                when others =>
                    null;
            end case;
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
end rtl;
