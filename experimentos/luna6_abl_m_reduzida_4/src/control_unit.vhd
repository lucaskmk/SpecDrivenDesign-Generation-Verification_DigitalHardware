library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity control_unit is
    port(
        instr : in std_logic_vector(31 downto 0);
        reg_write : out std_logic;
        mem_write : out std_logic;
        data_width : out std_logic_vector(1 downto 0);
        alu_src_a_pc : out std_logic;
        alu_src_b_imm : out std_logic;
        alu_op : out std_logic_vector(4 downto 0);
        wb_sel : out std_logic_vector(1 downto 0);
        imm_sel : out std_logic_vector(2 downto 0);
        branch : out std_logic;
        jal : out std_logic;
        jalr : out std_logic
    );
end control_unit;

architecture rtl of control_unit is
begin
    decode : process(all)
        variable all_binary : boolean;
    begin
        reg_write <= '0';
        mem_write <= '0';
        data_width <= "10";
        alu_src_a_pc <= '0';
        alu_src_b_imm <= '0';
        alu_op <= "00000";
        wb_sel <= "00";
        imm_sel <= "000";
        branch <= '0';
        jal <= '0';
        jalr <= '0';

        all_binary := true;
        for i in instr'range loop
            if instr(i) /= '0' and instr(i) /= '1' then
                all_binary := false;
            end if;
        end loop;

        if all_binary then
            case instr(6 downto 0) is
                when "0110011" =>
                    case instr(14 downto 12) is
                        when "000" =>
                            case instr(31 downto 25) is
                                when "0000000" => alu_op <= "00000";
                                when "0100000" => alu_op <= "00001";
                                when "0000001" => alu_op <= "01111";
                                when others => null;
                            end case;
                            if instr(31 downto 25) = "0000000" or
                               instr(31 downto 25) = "0100000" or
                               instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                wb_sel <= "00";
                            end if;
                        when "001" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "00010";
                                wb_sel <= "00";
                            elsif instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                alu_op <= "10000";
                                wb_sel <= "00";
                            end if;
                        when "010" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "00011";
                                wb_sel <= "00";
                            elsif instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                alu_op <= "10001";
                                wb_sel <= "00";
                            end if;
                        when "011" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "00100";
                                wb_sel <= "00";
                            elsif instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                alu_op <= "10010";
                                wb_sel <= "00";
                            end if;
                        when "100" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "00101";
                                wb_sel <= "00";
                            elsif instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                alu_op <= "10011";
                                wb_sel <= "00";
                            end if;
                        when "101" =>
                            case instr(31 downto 25) is
                                when "0000000" =>
                                    reg_write <= '1';
                                    alu_op <= "00110";
                                    wb_sel <= "00";
                                when "0100000" =>
                                    reg_write <= '1';
                                    alu_op <= "00111";
                                    wb_sel <= "00";
                                when "0000001" =>
                                    reg_write <= '1';
                                    alu_op <= "10100";
                                    wb_sel <= "00";
                                when others => null;
                            end case;
                        when "110" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "01000";
                                wb_sel <= "00";
                            elsif instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                alu_op <= "10101";
                                wb_sel <= "00";
                            end if;
                        when "111" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "01001";
                                wb_sel <= "00";
                            elsif instr(31 downto 25) = "0000001" then
                                reg_write <= '1';
                                alu_op <= "10110";
                                wb_sel <= "00";
                            end if;
                        when others => null;
                    end case;

                when "0010011" =>
                    case instr(14 downto 12) is
                        when "000" =>
                            reg_write <= '1';
                            alu_op <= "00000";
                        when "001" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "00010";
                            end if;
                        when "010" =>
                            reg_write <= '1';
                            alu_op <= "00011";
                        when "011" =>
                            reg_write <= '1';
                            alu_op <= "00100";
                        when "100" =>
                            reg_write <= '1';
                            alu_op <= "00101";
                        when "101" =>
                            if instr(31 downto 25) = "0000000" then
                                reg_write <= '1';
                                alu_op <= "00110";
                            elsif instr(31 downto 25) = "0100000" then
                                reg_write <= '1';
                                alu_op <= "00111";
                            end if;
                        when "110" =>
                            reg_write <= '1';
                            alu_op <= "01000";
                        when "111" =>
                            reg_write <= '1';
                            alu_op <= "01001";
                        when others => null;
                    end case;

                    if reg_write = '1' then
                        alu_src_b_imm <= '1';
                        wb_sel <= "00";
                        imm_sel <= "001";
                    end if;

                when "0000011" =>
                    case instr(14 downto 12) is
                        when "000" | "100" =>
                            reg_write <= '1';
                            data_width <= "00";
                        when "001" | "101" =>
                            reg_write <= '1';
                            data_width <= "01";
                        when "010" =>
                            reg_write <= '1';
                            data_width <= "10";
                        when others => null;
                    end case;
                    if instr(14 downto 12) = "000" or
                       instr(14 downto 12) = "001" or
                       instr(14 downto 12) = "010" or
                       instr(14 downto 12) = "100" or
                       instr(14 downto 12) = "101" then
                        alu_src_b_imm <= '1';
                        wb_sel <= "01";
                        imm_sel <= "001";
                    end if;

                when "0100011" =>
                    case instr(14 downto 12) is
                        when "000" =>
                            mem_write <= '1';
                            data_width <= "00";
                        when "001" =>
                            mem_write <= '1';
                            data_width <= "01";
                        when "010" =>
                            mem_write <= '1';
                            data_width <= "10";
                        when others => null;
                    end case;
                    if instr(14 downto 12) = "000" or
                       instr(14 downto 12) = "001" or
                       instr(14 downto 12) = "010" then
                        alu_src_b_imm <= '1';
                        imm_sel <= "010";
                    end if;

                when "1100011" =>
                    case instr(14 downto 12) is
                        when "000" => alu_op <= "01011";
                        when "001" => alu_op <= "01100";
                        when "100" => alu_op <= "00011";
                        when "101" => alu_op <= "01101";
                        when "110" => alu_op <= "00100";
                        when "111" => alu_op <= "01110";
                        when others => null;
                    end case;
                    if instr(14 downto 12) = "000" or
                       instr(14 downto 12) = "001" or
                       instr(14 downto 12) = "100" or
                       instr(14 downto 12) = "101" or
                       instr(14 downto 12) = "110" or
                       instr(14 downto 12) = "111" then
                        branch <= '1';
                        imm_sel <= "011";
                    end if;

                when "0110111" =>
                    reg_write <= '1';
                    alu_src_b_imm <= '1';
                    alu_op <= "01010";
                    imm_sel <= "100";

                when "0010111" =>
                    reg_write <= '1';
                    alu_src_a_pc <= '1';
                    alu_src_b_imm <= '1';
                    imm_sel <= "100";

                when "1101111" =>
                    reg_write <= '1';
                    alu_src_a_pc <= '1';
                    alu_src_b_imm <= '1';
                    wb_sel <= "10";
                    imm_sel <= "101";
                    jal <= '1';

                when "1100111" =>
                    if instr(14 downto 12) = "000" then
                        reg_write <= '1';
                        alu_src_b_imm <= '1';
                        wb_sel <= "10";
                        imm_sel <= "001";
                        jalr <= '1';
                    end if;

                when others => null;
            end case;
        end if;
    end process;
end rtl;
