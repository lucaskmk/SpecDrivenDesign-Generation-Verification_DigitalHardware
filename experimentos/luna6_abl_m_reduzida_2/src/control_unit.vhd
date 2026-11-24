library ieee;
use ieee.std_logic_1164.all;

entity control_unit is
    port(
        opcode        : in  std_logic_vector(6 downto 0);
        funct3        : in  std_logic_vector(2 downto 0);
        rd_write      : out std_logic;
        mem_write     : out std_logic;
        load_enable   : out std_logic;
        data_width    : out std_logic_vector(1 downto 0);
        load_signed   : out std_logic;
        alu_a_pc      : out std_logic;
        alu_b_imm     : out std_logic;
        wb_sel        : out std_logic_vector(1 downto 0);
        branch_enable : out std_logic;
        jal           : out std_logic;
        jalr          : out std_logic
    );
end control_unit;

architecture rtl of control_unit is
begin
    process(opcode, funct3)
    begin
        rd_write      <= '0';
        mem_write     <= '0';
        load_enable   <= '0';
        data_width    <= "10";
        load_signed   <= '0';
        alu_a_pc      <= '0';
        alu_b_imm     <= '0';
        wb_sel        <= "00";
        branch_enable <= '0';
        jal           <= '0';
        jalr          <= '0';

        case opcode is
            when "0110011" => -- OP
                rd_write <= '1';

            when "0010011" => -- OP-IMM
                rd_write  <= '1';
                alu_b_imm <= '1';

            when "0110111" => -- LUI
                rd_write  <= '1';
                alu_b_imm <= '1';

            when "0010111" => -- AUIPC
                rd_write  <= '1';
                alu_a_pc  <= '1';
                alu_b_imm <= '1';

            when "0000011" => -- Loads
                case funct3 is
                    when "000" => -- LB
                        rd_write    <= '1';
                        load_enable <= '1';
                        data_width  <= "00";
                        load_signed <= '1';
                        alu_b_imm   <= '1';
                        wb_sel      <= "01";

                    when "001" => -- LH
                        rd_write    <= '1';
                        load_enable <= '1';
                        data_width  <= "01";
                        load_signed <= '1';
                        alu_b_imm   <= '1';
                        wb_sel      <= "01";

                    when "010" => -- LW
                        rd_write    <= '1';
                        load_enable <= '1';
                        data_width  <= "10";
                        alu_b_imm   <= '1';
                        wb_sel      <= "01";

                    when "100" => -- LBU
                        rd_write    <= '1';
                        load_enable <= '1';
                        data_width  <= "00";
                        alu_b_imm   <= '1';
                        wb_sel      <= "01";

                    when "101" => -- LHU
                        rd_write    <= '1';
                        load_enable <= '1';
                        data_width  <= "01";
                        alu_b_imm   <= '1';
                        wb_sel      <= "01";

                    when others =>
                        null;
                end case;

            when "0100011" => -- Stores
                case funct3 is
                    when "000" => -- SB
                        mem_write <= '1';
                        data_width <= "00";
                        alu_b_imm <= '1';

                    when "001" => -- SH
                        mem_write <= '1';
                        data_width <= "01";
                        alu_b_imm <= '1';

                    when "010" => -- SW
                        mem_write <= '1';
                        data_width <= "10";
                        alu_b_imm <= '1';

                    when others =>
                        null;
                end case;

            when "1100011" => -- Conditional branches
                case funct3 is
                    when "000" | "001" | "100" | "101" | "110" | "111" =>
                        branch_enable <= '1';

                    when others =>
                        null;
                end case;

            when "1101111" => -- JAL
                rd_write  <= '1';
                alu_a_pc  <= '1';
                alu_b_imm <= '1';
                wb_sel    <= "10";
                jal       <= '1';

            when "1100111" => -- JALR
                if funct3 = "000" then
                    rd_write  <= '1';
                    alu_b_imm <= '1';
                    wb_sel    <= "10";
                    jalr      <= '1';
                end if;

            when others =>
                null;
        end case;
    end process;
end rtl;
