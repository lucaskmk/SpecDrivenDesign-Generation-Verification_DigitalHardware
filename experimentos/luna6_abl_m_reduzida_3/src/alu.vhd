library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity alu is
    port(
        instr       : in  std_logic_vector(31 downto 0);
        operand_a   : in  std_logic_vector(31 downto 0);
        operand_b   : in  std_logic_vector(31 downto 0);
        result      : out std_logic_vector(31 downto 0);
        branch_taken : out std_logic
    );
end alu;

architecture rtl of alu is
begin
    process(all)
        variable result_v    : std_logic_vector(31 downto 0);
        variable branch_v    : std_logic;
        variable opcode      : std_logic_vector(6 downto 0);
        variable funct3      : std_logic_vector(2 downto 0);
        variable funct7      : std_logic_vector(6 downto 0);
        variable shift_amount : natural range 0 to 31;
        variable product_ss  : signed(63 downto 0);
        variable product_su  : signed(64 downto 0);
        variable product_uu  : unsigned(63 downto 0);
    begin
        result_v := (others => '0');
        branch_v := '0';

        opcode := instr(6 downto 0);
        funct3 := instr(14 downto 12);
        funct7 := instr(31 downto 25);

        case opcode is
            when "0110011" =>
                case funct7 is
                    when "0000000" =>
                        case funct3 is
                            when "000" =>
                                result_v := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));
                            when "001" =>
                                result_v := std_logic_vector(shift_left(unsigned(operand_a), to_integer(unsigned(operand_b(4 downto 0)))));
                            when "010" =>
                                if signed(operand_a) < signed(operand_b) then
                                    result_v := x"00000001";
                                end if;
                            when "011" =>
                                if unsigned(operand_a) < unsigned(operand_b) then
                                    result_v := x"00000001";
                                end if;
                            when "100" =>
                                result_v := operand_a xor operand_b;
                            when "101" =>
                                result_v := std_logic_vector(shift_right(unsigned(operand_a), to_integer(unsigned(operand_b(4 downto 0)))));
                            when "110" =>
                                result_v := operand_a or operand_b;
                            when "111" =>
                                result_v := operand_a and operand_b;
                            when others =>
                                null;
                        end case;

                    when "0100000" =>
                        case funct3 is
                            when "000" =>
                                result_v := std_logic_vector(unsigned(operand_a) - unsigned(operand_b));
                            when "101" =>
                                result_v := std_logic_vector(shift_right(signed(operand_a), to_integer(unsigned(operand_b(4 downto 0)))));
                            when others =>
                                null;
                        end case;

                    when "0000001" =>
                        case funct3 is
                            when "000" =>
                                product_uu := unsigned(operand_a) * unsigned(operand_b);
                                result_v := std_logic_vector(product_uu(31 downto 0));
                            when "001" =>
                                product_ss := signed(operand_a) * signed(operand_b);
                                result_v := std_logic_vector(product_ss(63 downto 32));
                            when "010" =>
                                product_su := signed(operand_a) * signed('0' & operand_b);
                                result_v := std_logic_vector(product_su(63 downto 32));
                            when "011" =>
                                product_uu := unsigned(operand_a) * unsigned(operand_b);
                                result_v := std_logic_vector(product_uu(63 downto 32));
                            when "100" =>
                                if operand_b = x"00000000" then
                                    result_v := x"FFFFFFFF";
                                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                                    result_v := x"80000000";
                                else
                                    result_v := std_logic_vector(signed(operand_a) / signed(operand_b));
                                end if;
                            when "101" =>
                                if operand_b = x"00000000" then
                                    result_v := x"FFFFFFFF";
                                else
                                    result_v := std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                                end if;
                            when "110" =>
                                if operand_b = x"00000000" then
                                    result_v := operand_a;
                                elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                                    result_v := x"00000000";
                                else
                                    result_v := std_logic_vector(signed(operand_a) rem signed(operand_b));
                                end if;
                            when "111" =>
                                if operand_b = x"00000000" then
                                    result_v := operand_a;
                                else
                                    result_v := std_logic_vector(unsigned(operand_a) rem unsigned(operand_b));
                                end if;
                            when others =>
                                null;
                        end case;

                    when others =>
                        null;
                end case;

            when "0010011" =>
                case funct3 is
                    when "000" =>
                        result_v := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));
                    when "001" =>
                        if funct7 = "0000000" then
                            shift_amount := to_integer(unsigned(instr(24 downto 20)));
                            result_v := std_logic_vector(shift_left(unsigned(operand_a), shift_amount));
                        end if;
                    when "010" =>
                        if signed(operand_a) < signed(operand_b) then
                            result_v := x"00000001";
                        end if;
                    when "011" =>
                        if unsigned(operand_a) < unsigned(operand_b) then
                            result_v := x"00000001";
                        end if;
                    when "100" =>
                        result_v := operand_a xor operand_b;
                    when "101" =>
                        shift_amount := to_integer(unsigned(instr(24 downto 20)));
                        if funct7 = "0000000" then
                            result_v := std_logic_vector(shift_right(unsigned(operand_a), shift_amount));
                        elsif funct7 = "0100000" then
                            result_v := std_logic_vector(shift_right(signed(operand_a), shift_amount));
                        end if;
                    when "110" =>
                        result_v := operand_a or operand_b;
                    when "111" =>
                        result_v := operand_a and operand_b;
                    when others =>
                        null;
                end case;

            when "1100011" =>
                case funct3 is
                    when "000" =>
                        if operand_a = operand_b then
                            branch_v := '1';
                        end if;
                    when "001" =>
                        if operand_a /= operand_b then
                            branch_v := '1';
                        end if;
                    when "100" =>
                        if signed(operand_a) < signed(operand_b) then
                            branch_v := '1';
                        end if;
                    when "101" =>
                        if signed(operand_a) >= signed(operand_b) then
                            branch_v := '1';
                        end if;
                    when "110" =>
                        if unsigned(operand_a) < unsigned(operand_b) then
                            branch_v := '1';
                        end if;
                    when "111" =>
                        if unsigned(operand_a) >= unsigned(operand_b) then
                            branch_v := '1';
                        end if;
                    when others =>
                        null;
                end case;

            when others =>
                null;
        end case;

        result <= result_v;
        branch_taken <= branch_v;
    end process;
end rtl;
