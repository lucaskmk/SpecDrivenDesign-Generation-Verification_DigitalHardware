library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity decoder is
    port(
        instr : in std_logic_vector(31 downto 0);
        reg_write : out std_logic;
        mem_write : out std_logic;
        alu_src_a_pc : out std_logic;
        alu_src_b_imm : out std_logic;
        alu_control : out std_logic_vector(3 downto 0);
        branch_enable : out std_logic;
        jump : out std_logic;
        jalr : out std_logic;
        wb_select : out std_logic_vector(1 downto 0)
    );
end entity decoder;

architecture rtl of decoder is
begin
    process(all)
    begin
        reg_write     <= '0';
        mem_write     <= '0';
        alu_src_a_pc  <= '0';
        alu_src_b_imm <= '0';
        alu_control   <= "0000";
        branch_enable <= '0';
        jump          <= '0';
        jalr          <= '0';
        wb_select     <= "00";

        case instr(6 downto 0) is
            when "0110011" => -- OP
                if instr(31 downto 25) = "0000001" then
                    -- RV32M operations use the register operands and default ALU control.
                    reg_write <= '1';
                else
                    case instr(14 downto 12) is
                        when "000" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "0000";
                            elsif instr(31 downto 25) = "0100000" then
                                reg_write <= '1';
                                alu_control <= "0001";
                            end if;
                        when "001" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "0010";
                            end if;
                        when "010" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "0011";
                            end if;
                        when "011" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "0100";
                            end if;
                        when "100" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "0101";
                            end if;
                        when "101" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "0110";
                            elsif instr(31 downto 25) = "0100000" then
                                reg_write <= '1';
                                alu_control <= "0111";
                            end if;
                        when "110" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "1000";
                            end if;
                        when "111" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_control <= "1001";
                            end if;
                        when others =>
                            null;
                    end case;
                end if;

            when "0010011" => -- OP-IMM
                case instr(14 downto 12) is
                    when "000" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "0000";
                    when "001" =>
                        if instr(31 downto 25) = "0000000" then
                            reg_write <= '1';
                            alu_src_b_imm <= '1';
                            alu_control <= "0010";
                        end if;
                    when "010" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "0011";
                    when "011" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "0100";
                    when "100" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "0101";
                    when "101" =>
                        if instr(31 downto 25) = "0000000" then
                            reg_write <= '1';
                            alu_src_b_imm <= '1';
                            alu_control <= "0110";
                        elsif instr(31 downto 25) = "0100000" then
                            reg_write <= '1';
                            alu_src_b_imm <= '1';
                            alu_control <= "0111";
                        end if;
                    when "110" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "1000";
                    when "111" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "1001";
                    when others =>
                        null;
                end case;

            when "0000011" => -- Loads
                case instr(14 downto 12) is
                    when "000" | "001" | "010" | "100" | "101" =>
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "0000";
                        wb_select <= "01";
                    when others =>
                        null;
                end case;

            when "0100011" => -- Stores
                case instr(14 downto 12) is
                    when "000" | "001" | "010" =>
                        mem_write <= '1';
                        alu_src_b_imm <= '1';
                        alu_control <= "0000";
                    when others =>
                        null;
                end case;

            when "1100011" => -- Conditional branches
                case instr(14 downto 12) is
                    when "000" =>
                        branch_enable <= '1';
                        alu_control <= "0000";
                    when "001" =>
                        branch_enable <= '1';
                        alu_control <= "0001";
                    when "100" =>
                        branch_enable <= '1';
                        alu_control <= "0010";
                    when "101" =>
                        branch_enable <= '1';
                        alu_control <= "0011";
                    when "110" =>
                        branch_enable <= '1';
                        alu_control <= "0100";
                    when "111" =>
                        branch_enable <= '1';
                        alu_control <= "0101";
                    when others =>
                        null;
                end case;

            when "0110111" => -- LUI
                reg_write <= '1';
                alu_src_b_imm <= '1';
                alu_control <= "1010";

            when "0010111" => -- AUIPC
                reg_write <= '1';
                alu_src_a_pc <= '1';
                alu_src_b_imm <= '1';
                alu_control <= "0000";

            when "1101111" => -- JAL
                reg_write <= '1';
                alu_src_a_pc <= '1';
                alu_src_b_imm <= '1';
                jump <= '1';
                wb_select <= "10";

            when "1100111" => -- JALR
                if instr(14 downto 12) = "000" then
                    reg_write <= '1';
                    alu_src_b_imm <= '1';
                    jump <= '1';
                    jalr <= '1';
                    wb_select <= "10";
                    alu_control <= "0000";
                end if;

            when others =>
                null;
        end case;
    end process;
end architecture rtl;
