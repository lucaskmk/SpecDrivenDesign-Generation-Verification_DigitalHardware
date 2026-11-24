library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity control_unit is
    port(
        instr         : in  std_logic_vector(31 downto 0);
        imm_i         : out std_logic_vector(31 downto 0);
        imm_s         : out std_logic_vector(31 downto 0);
        imm_b         : out std_logic_vector(31 downto 0);
        imm_u         : out std_logic_vector(31 downto 0);
        imm_j         : out std_logic_vector(31 downto 0);
        reg_write     : out std_logic;
        mem_write     : out std_logic;
        mem_width     : out std_logic_vector(1 downto 0);
        is_load       : out std_logic;
        load_funct3   : out std_logic_vector(2 downto 0);
        alu_src_imm   : out std_logic;
        writeback_sel : out std_logic_vector(1 downto 0)
    );
end control_unit;

architecture rtl of control_unit is
begin
    process(instr)
        variable opcode : std_logic_vector(6 downto 0);
        variable funct3 : std_logic_vector(2 downto 0);
        variable funct7 : std_logic_vector(6 downto 0);
    begin
        imm_i <= std_logic_vector(resize(signed(instr(31 downto 20)), 32));
        imm_s <= std_logic_vector(resize(signed(instr(31 downto 25) & instr(11 downto 7)), 32));
        imm_b <= std_logic_vector(resize(signed(instr(31) & instr(7) & instr(30 downto 25) & instr(11 downto 8) & '0'), 32));
        imm_u <= instr(31 downto 12) & x"000";
        imm_j <= std_logic_vector(resize(signed(instr(31) & instr(19 downto 12) & instr(20) & instr(30 downto 21) & '0'), 32));

        reg_write     <= '0';
        mem_write     <= '0';
        mem_width     <= "10";
        is_load       <= '0';
        load_funct3   <= "000";
        alu_src_imm   <= '0';
        writeback_sel <= "00";

        opcode := instr(6 downto 0);
        funct3 := instr(14 downto 12);
        funct7 := instr(31 downto 25);

        case opcode is
            when "0110111" =>  -- LUI
                reg_write     <= '1';
                writeback_sel <= "11";

            when "0010111" =>  -- AUIPC
                reg_write   <= '1';
                alu_src_imm <= '1';

            when "1101111" =>  -- JAL
                reg_write     <= '1';
                writeback_sel <= "10";

            when "1100111" =>  -- JALR
                if funct3 = "000" then
                    reg_write     <= '1';
                    alu_src_imm   <= '1';
                    writeback_sel <= "10";
                end if;

            when "0000011" =>  -- Loads
                case funct3 is
                    when "000" | "100" =>
                        is_load       <= '1';
                        reg_write     <= '1';
                        alu_src_imm   <= '1';
                        mem_width     <= "00";
                        load_funct3   <= funct3;
                        writeback_sel <= "01";
                    when "001" | "101" =>
                        is_load       <= '1';
                        reg_write     <= '1';
                        alu_src_imm   <= '1';
                        mem_width     <= "01";
                        load_funct3   <= funct3;
                        writeback_sel <= "01";
                    when "010" =>
                        is_load       <= '1';
                        reg_write     <= '1';
                        alu_src_imm   <= '1';
                        mem_width     <= "10";
                        load_funct3   <= funct3;
                        writeback_sel <= "01";
                    when others =>
                        null;
                end case;

            when "0100011" =>  -- Stores
                case funct3 is
                    when "000" =>
                        mem_write   <= '1';
                        mem_width   <= "00";
                        alu_src_imm <= '1';
                    when "001" =>
                        mem_write   <= '1';
                        mem_width   <= "01";
                        alu_src_imm <= '1';
                    when "010" =>
                        mem_write   <= '1';
                        mem_width   <= "10";
                        alu_src_imm <= '1';
                    when others =>
                        null;
                end case;

            when "0010011" =>  -- OP-IMM
                case funct3 is
                    when "000" | "010" | "011" | "100" | "110" | "111" =>
                        reg_write   <= '1';
                        alu_src_imm <= '1';
                    when "001" =>
                        if funct7 = "0000000" then
                            reg_write   <= '1';
                            alu_src_imm <= '1';
                        end if;
                    when "101" =>
                        if funct7 = "0000000" or funct7 = "0100000" then
                            reg_write   <= '1';
                            alu_src_imm <= '1';
                        end if;
                    when others =>
                        null;
                end case;

            when "0110011" =>  -- OP and RV32M
                if funct7 = "0000001" or funct7 = "0000000" then
                    reg_write <= '1';
                elsif funct7 = "0100000" and (funct3 = "000" or funct3 = "101") then
                    reg_write <= '1';
                end if;

            when others =>
                null;
        end case;
    end process;
end rtl;
