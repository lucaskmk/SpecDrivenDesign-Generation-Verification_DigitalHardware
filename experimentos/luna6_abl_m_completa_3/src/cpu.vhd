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
    signal pc                : std_logic_vector(31 downto 0);
    signal pc_plus_4         : std_logic_vector(31 downto 0);
    signal pc_next           : std_logic_vector(31 downto 0);

    signal rs1_data          : std_logic_vector(31 downto 0);
    signal rs2_data          : std_logic_vector(31 downto 0);
    signal rd_data           : std_logic_vector(31 downto 0);
    signal rd_write          : std_logic;

    signal imm_i             : std_logic_vector(31 downto 0);
    signal imm_s             : std_logic_vector(31 downto 0);
    signal imm_b             : std_logic_vector(31 downto 0);
    signal imm_u             : std_logic_vector(31 downto 0);
    signal imm_j             : std_logic_vector(31 downto 0);

    signal alu_operand_a     : std_logic_vector(31 downto 0);
    signal alu_operand_b     : std_logic_vector(31 downto 0);
    signal alu_result        : std_logic_vector(31 downto 0);
    signal branch_taken      : std_logic;

    signal effective_addr    : std_logic_vector(31 downto 0);
    signal load_value        : std_logic_vector(31 downto 0);
    signal valid_store       : std_logic;
    signal valid_jalr        : std_logic;

    function valid_register_write(
        op : std_logic_vector(6 downto 0);
        f3 : std_logic_vector(2 downto 0);
        f7 : std_logic_vector(6 downto 0)
    ) return std_logic is
    begin
        case op is
            when "0110011" =>
                case f3 is
                    when "000" =>
                        if f7 = "0000000" or f7 = "0100000" or f7 = "0000001" then
                            return '1';
                        end if;
                    when "001" | "010" | "011" | "100" | "110" | "111" =>
                        if f7 = "0000000" or f7 = "0000001" then
                            return '1';
                        end if;
                    when "101" =>
                        if f7 = "0000000" or f7 = "0100000" or f7 = "0000001" then
                            return '1';
                        end if;
                    when others =>
                        null;
                end case;
            when "0010011" =>
                case f3 is
                    when "000" | "010" | "011" | "100" | "110" | "111" =>
                        return '1';
                    when "001" =>
                        if f7 = "0000000" then
                            return '1';
                        end if;
                    when "101" =>
                        if f7 = "0000000" or f7 = "0100000" then
                            return '1';
                        end if;
                    when others =>
                        null;
                end case;
            when "0000011" =>
                if f3 = "000" or f3 = "001" or f3 = "010" or
                   f3 = "100" or f3 = "101" then
                    return '1';
                end if;
            when "0110111" | "0010111" | "1101111" =>
                return '1';
            when "1100111" =>
                if f3 = "000" then
                    return '1';
                end if;
            when others =>
                null;
        end case;
        return '0';
    end function;

    function valid_store_instruction(
        op : std_logic_vector(6 downto 0);
        f3 : std_logic_vector(2 downto 0)
    ) return std_logic is
    begin
        if op = "0100011" and
           (f3 = "000" or f3 = "001" or f3 = "010") then
            return '1';
        end if;
        return '0';
    end function;
begin
    instr_addr <= pc;

    pc_plus_4 <= std_logic_vector(unsigned(pc) + to_unsigned(4, 32));

    u_register_file : entity work.register_file
        port map(
            clk      => clk,
            rst      => rst,
            rs1_addr => instr_data(19 downto 15),
            rs2_addr => instr_data(24 downto 20),
            rs1_data => rs1_data,
            rs2_data => rs2_data,
            rd_addr  => instr_data(11 downto 7),
            rd_data  => rd_data,
            rd_write => rd_write
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

    alu_operand_a <= rs1_data;

    process(all)
    begin
        if instr_data(6 downto 0) = "0010011" then
            alu_operand_b <= imm_i;
        else
            alu_operand_b <= rs2_data;
        end if;
    end process;

    u_alu : entity work.alu
        port map(
            opcode       => instr_data(6 downto 0),
            funct3       => instr_data(14 downto 12),
            funct7       => instr_data(31 downto 25),
            operand_a    => alu_operand_a,
            operand_b    => alu_operand_b,
            result       => alu_result,
            branch_taken => branch_taken
        );

    valid_store <= valid_store_instruction(
        instr_data(6 downto 0),
        instr_data(14 downto 12)
    );

    valid_jalr <= '1' when
        instr_data(6 downto 0) = "1100111" and
        instr_data(14 downto 12) = "000"
        else '0';

    effective_addr <= std_logic_vector(unsigned(rs1_data) + unsigned(imm_s))
        when instr_data(6 downto 0) = "0100011" else
        std_logic_vector(unsigned(rs1_data) + unsigned(imm_i));

    process(all)
        variable byte_value : std_logic_vector(7 downto 0);
        variable half_value : std_logic_vector(15 downto 0);
    begin
        load_value <= (others => '0');
        byte_value := (others => '0');
        half_value := (others => '0');

        case effective_addr(1 downto 0) is
            when "00" => byte_value := data_read_data(7 downto 0);
            when "01" => byte_value := data_read_data(15 downto 8);
            when "10" => byte_value := data_read_data(23 downto 16);
            when "11" => byte_value := data_read_data(31 downto 24);
            when others => null;
        end case;

        if effective_addr(1) = '0' then
            half_value := data_read_data(15 downto 0);
        else
            half_value := data_read_data(31 downto 16);
        end if;

        if instr_data(6 downto 0) = "0000011" then
            case instr_data(14 downto 12) is
                when "000" =>
                    load_value <= std_logic_vector(resize(signed(byte_value), 32));
                when "001" =>
                    load_value <= std_logic_vector(resize(signed(half_value), 32));
                when "010" =>
                    load_value <= data_read_data;
                when "100" =>
                    load_value <= std_logic_vector(resize(unsigned(byte_value), 32));
                when "101" =>
                    load_value <= std_logic_vector(resize(unsigned(half_value), 32));
                when others =>
                    load_value <= (others => '0');
            end case;
        end if;
    end process;

    process(all)
    begin
        data_addr       <= (others => '0');
        data_write      <= '0';
        data_width      <= "10";
        data_write_data <= (others => '0');

        if instr_data(6 downto 0) = "0000011" then
            case instr_data(14 downto 12) is
                when "000" | "100" =>
                    data_addr  <= effective_addr;
                    data_width <= "00";
                when "001" | "101" =>
                    data_addr  <= effective_addr;
                    data_width <= "01";
                when "010" =>
                    data_addr  <= effective_addr;
                    data_width <= "10";
                when others =>
                    null;
            end case;
        elsif valid_store = '1' then
            data_addr       <= effective_addr;
            data_write_data <= rs2_data;
            data_write      <= not rst;
            case instr_data(14 downto 12) is
                when "000" => data_width <= "00";
                when "001" => data_width <= "01";
                when "010" => data_width <= "10";
                when others => null;
            end case;
        end if;
    end process;

    process(all)
    begin
        rd_data <= (others => '0');

        case instr_data(6 downto 0) is
            when "0110011" | "0010011" =>
                rd_data <= alu_result;
            when "0000011" =>
                rd_data <= load_value;
            when "0110111" =>
                rd_data <= imm_u;
            when "0010111" =>
                rd_data <= std_logic_vector(unsigned(pc) + unsigned(imm_u));
            when "1101111" | "1100111" =>
                rd_data <= pc_plus_4;
            when others =>
                null;
        end case;
    end process;

    rd_write <= valid_register_write(
        instr_data(6 downto 0),
        instr_data(14 downto 12),
        instr_data(31 downto 25)
    ) and not rst;

    process(all)
    begin
        pc_next <= pc_plus_4;

        if instr_data(6 downto 0) = "1101111" then
            pc_next <= std_logic_vector(unsigned(pc) + unsigned(imm_j));
        elsif valid_jalr = '1' then
            pc_next <= (std_logic_vector(unsigned(rs1_data) + unsigned(imm_i)) and
                        x"FFFFFFFE");
        elsif instr_data(6 downto 0) = "1100011" and branch_taken = '1' then
            pc_next <= std_logic_vector(unsigned(pc) + unsigned(imm_b));
        end if;
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
