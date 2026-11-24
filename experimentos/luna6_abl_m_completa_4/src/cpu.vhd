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
    signal next_pc : std_logic_vector(31 downto 0);

    signal imm_i : std_logic_vector(31 downto 0);
    signal imm_s : std_logic_vector(31 downto 0);
    signal imm_b : std_logic_vector(31 downto 0);
    signal imm_u : std_logic_vector(31 downto 0);
    signal imm_j : std_logic_vector(31 downto 0);

    signal rf_read_data1 : std_logic_vector(31 downto 0);
    signal rf_read_data2 : std_logic_vector(31 downto 0);
    signal rf_write_enable : std_logic;
    signal rf_write_data : std_logic_vector(31 downto 0);

    signal exec_operand_a : std_logic_vector(31 downto 0);
    signal exec_operand_b : std_logic_vector(31 downto 0);
    signal exec_result : std_logic_vector(31 downto 0);
    signal exec_branch_taken : std_logic;

    signal jal_valid : std_logic;
    signal jalr_valid : std_logic;
    signal branch_valid : std_logic;

    function valid_op(
        f3 : std_logic_vector(2 downto 0);
        f7 : std_logic_vector(6 downto 0)
    ) return boolean is
    begin
        case f3 is
            when "000" =>
                return f7 = "0000000" or f7 = "0100000" or f7 = "0000001";
            when "001" =>
                return f7 = "0000000" or f7 = "0000001";
            when "010" | "011" | "100" | "110" | "111" =>
                return f7 = "0000000" or f7 = "0000001";
            when "101" =>
                return f7 = "0000000" or f7 = "0100000" or f7 = "0000001";
            when others =>
                return false;
        end case;
    end function;

    function valid_op_imm(
        f3 : std_logic_vector(2 downto 0);
        f7 : std_logic_vector(6 downto 0)
    ) return boolean is
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

    function valid_branch(
        f3 : std_logic_vector(2 downto 0)
    ) return boolean is
    begin
        case f3 is
            when "000" | "001" | "100" | "101" | "110" | "111" =>
                return true;
            when others =>
                return false;
        end case;
    end function;
begin
    instr_addr <= pc;

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
            read_addr1 => instr_data(19 downto 15),
            read_addr2 => instr_data(24 downto 20),
            read_data1 => rf_read_data1,
            read_data2 => rf_read_data2,
            write_enable => rf_write_enable,
            write_addr => instr_data(11 downto 7),
            write_data => rf_write_data
        );

    process(all)
    begin
        exec_operand_a <= rf_read_data1;
        exec_operand_b <= rf_read_data2;

        if instr_data(6 downto 0) = "0010011" then
            exec_operand_b <= imm_i;
        elsif instr_data(6 downto 0) = "0010111" then
            exec_operand_a <= pc;
            exec_operand_b <= imm_u;
        end if;
    end process;

    u_execution_unit : entity work.execution_unit
        port map (
            opcode => instr_data(6 downto 0),
            funct3 => instr_data(14 downto 12),
            funct7 => instr_data(31 downto 25),
            operand_a => exec_operand_a,
            operand_b => exec_operand_b,
            result => exec_result,
            branch_taken => exec_branch_taken
        );

    jal_valid <= '1' when instr_data(6 downto 0) = "1101111" else '0';

    jalr_valid <= '1'
        when instr_data(6 downto 0) = "1100111"
          and instr_data(14 downto 12) = "000"
        else '0';

    branch_valid <= '1'
        when instr_data(6 downto 0) = "1100011"
          and valid_branch(instr_data(14 downto 12))
        else '0';

    process(all)
        variable write_enable_v : std_logic;
        variable write_data_v : std_logic_vector(31 downto 0);
        variable data_addr_v : std_logic_vector(31 downto 0);
        variable data_write_v : std_logic;
        variable data_width_v : std_logic_vector(1 downto 0);
        variable data_write_data_v : std_logic_vector(31 downto 0);
        variable effective_addr_v : std_logic_vector(31 downto 0);
        variable selected_byte_v : std_logic_vector(7 downto 0);
        variable selected_half_v : std_logic_vector(15 downto 0);
    begin
        write_enable_v := '0';
        write_data_v := exec_result;
        data_addr_v := (others => '0');
        data_write_v := '0';
        data_width_v := "10";
        data_write_data_v := (others => '0');
        effective_addr_v := (others => '0');
        selected_byte_v := (others => '0');
        selected_half_v := (others => '0');

        if rst = '0' then
            case instr_data(6 downto 0) is
                when "0110111" =>
                    write_enable_v := '1';
                    write_data_v := imm_u;

                when "0010111" =>
                    write_enable_v := '1';
                    write_data_v := exec_result;

                when "1101111" =>
                    write_enable_v := '1';
                    write_data_v := std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

                when "1100111" =>
                    if instr_data(14 downto 12) = "000" then
                        write_enable_v := '1';
                        write_data_v := std_logic_vector(unsigned(pc) + to_unsigned(4, 32));
                    end if;

                when "0000011" =>
                    case instr_data(14 downto 12) is
                        when "000" | "100" =>
                            effective_addr_v :=
                                std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_i));
                            data_addr_v := effective_addr_v;
                            data_width_v := "00";
                            case effective_addr_v(1 downto 0) is
                                when "00" => selected_byte_v := data_read_data(7 downto 0);
                                when "01" => selected_byte_v := data_read_data(15 downto 8);
                                when "10" => selected_byte_v := data_read_data(23 downto 16);
                                when others => selected_byte_v := data_read_data(31 downto 24);
                            end case;
                            if instr_data(14 downto 12) = "000" then
                                write_data_v := std_logic_vector(resize(signed(selected_byte_v), 32));
                            else
                                write_data_v := std_logic_vector(resize(unsigned(selected_byte_v), 32));
                            end if;
                            write_enable_v := '1';

                        when "001" | "101" =>
                            effective_addr_v :=
                                std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_i));
                            data_addr_v := effective_addr_v;
                            data_width_v := "01";
                            if effective_addr_v(1) = '0' then
                                selected_half_v := data_read_data(15 downto 0);
                            else
                                selected_half_v := data_read_data(31 downto 16);
                            end if;
                            if instr_data(14 downto 12) = "001" then
                                write_data_v := std_logic_vector(resize(signed(selected_half_v), 32));
                            else
                                write_data_v := std_logic_vector(resize(unsigned(selected_half_v), 32));
                            end if;
                            write_enable_v := '1';

                        when "010" =>
                            effective_addr_v :=
                                std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_i));
                            data_addr_v := effective_addr_v;
                            data_width_v := "10";
                            write_data_v := data_read_data;
                            write_enable_v := '1';

                        when others =>
                            null;
                    end case;

                when "0100011" =>
                    case instr_data(14 downto 12) is
                        when "000" =>
                            data_addr_v :=
                                std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_s));
                            data_width_v := "00";
                            data_write_v := '1';
                            data_write_data_v := rf_read_data2;
                        when "001" =>
                            data_addr_v :=
                                std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_s));
                            data_width_v := "01";
                            data_write_v := '1';
                            data_write_data_v := rf_read_data2;
                        when "010" =>
                            data_addr_v :=
                                std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_s));
                            data_width_v := "10";
                            data_write_v := '1';
                            data_write_data_v := rf_read_data2;
                        when others =>
                            null;
                    end case;

                when "0010011" =>
                    if valid_op_imm(instr_data(14 downto 12), instr_data(31 downto 25)) then
                        write_enable_v := '1';
                        write_data_v := exec_result;
                    end if;

                when "0110011" =>
                    if valid_op(instr_data(14 downto 12), instr_data(31 downto 25)) then
                        write_enable_v := '1';
                        write_data_v := exec_result;
                    end if;

                when others =>
                    null;
            end case;
        end if;

        rf_write_enable <= write_enable_v;
        rf_write_data <= write_data_v;
        data_addr <= data_addr_v;
        data_write <= data_write_v;
        data_width <= data_width_v;
        data_write_data <= data_write_data_v;
    end process;

    process(all)
        variable target_v : std_logic_vector(31 downto 0);
    begin
        target_v := std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

        if jal_valid = '1' then
            target_v := std_logic_vector(unsigned(pc) + unsigned(imm_j));
        elsif jalr_valid = '1' then
            target_v := std_logic_vector(unsigned(rf_read_data1) + unsigned(imm_i));
            target_v(0) := '0';
        elsif branch_valid = '1' and exec_branch_taken = '1' then
            target_v := std_logic_vector(unsigned(pc) + unsigned(imm_b));
        end if;

        next_pc <= target_v;
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
