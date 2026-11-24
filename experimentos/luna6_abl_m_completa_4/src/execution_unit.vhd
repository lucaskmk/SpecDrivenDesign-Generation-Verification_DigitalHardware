library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity execution_unit is
    port(
        opcode : in std_logic_vector(6 downto 0);
        funct3 : in std_logic_vector(2 downto 0);
        funct7 : in std_logic_vector(6 downto 0);
        operand_a : in std_logic_vector(31 downto 0);
        operand_b : in std_logic_vector(31 downto 0);
        result : out std_logic_vector(31 downto 0);
        branch_taken : out std_logic
    );
end execution_unit;

architecture rtl of execution_unit is
begin
    process(all)
        variable result_value : std_logic_vector(31 downto 0);
        variable branch_value : std_logic;
        variable product_ss : signed(63 downto 0);
        variable product_hsu : signed(65 downto 0);
        variable product_uu : unsigned(63 downto 0);
        variable operand_a_33 : signed(32 downto 0);
        variable operand_b_33 : signed(32 downto 0);
        variable quotient_s : signed(31 downto 0);
        variable remainder_s : signed(31 downto 0);
        variable shift_amount : natural range 0 to 31;
    begin
        result_value := (others => '0');
        branch_value := '0';
        shift_amount := to_integer(unsigned(operand_b(4 downto 0)));

        case opcode is
            when "0010111" =>
                result_value := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));

            when "0110011" =>
                if funct7 = "0000001" then
                    case funct3 is
                        when "000" =>
                            product_uu := unsigned(operand_a) * unsigned(operand_b);
                            result_value := std_logic_vector(product_uu(31 downto 0));

                        when "001" =>
                            product_ss := signed(operand_a) * signed(operand_b);
                            result_value := std_logic_vector(product_ss(63 downto 32));

                        when "010" =>
                            operand_a_33 := resize(signed(operand_a), 33);
                            operand_b_33 := signed('0' & operand_b);
                            product_hsu := operand_a_33 * operand_b_33;
                            result_value := std_logic_vector(product_hsu(63 downto 32));

                        when "011" =>
                            product_uu := unsigned(operand_a) * unsigned(operand_b);
                            result_value := std_logic_vector(product_uu(63 downto 32));

                        when "100" =>
                            if operand_b = x"00000000" then
                                result_value := x"FFFFFFFF";
                            elsif operand_a = x"80000000" and
                                  operand_b = x"FFFFFFFF" then
                                result_value := x"80000000";
                            else
                                quotient_s := signed(operand_a) / signed(operand_b);
                                result_value := std_logic_vector(quotient_s);
                            end if;

                        when "101" =>
                            if operand_b = x"00000000" then
                                result_value := x"FFFFFFFF";
                            else
                                result_value := std_logic_vector(
                                    unsigned(operand_a) / unsigned(operand_b));
                            end if;

                        when "110" =>
                            if operand_b = x"00000000" then
                                result_value := operand_a;
                            elsif operand_a = x"80000000" and
                                  operand_b = x"FFFFFFFF" then
                                result_value := x"00000000";
                            else
                                remainder_s := signed(operand_a) rem signed(operand_b);
                                result_value := std_logic_vector(remainder_s);
                            end if;

                        when "111" =>
                            if operand_b = x"00000000" then
                                result_value := operand_a;
                            else
                                result_value := std_logic_vector(
                                    unsigned(operand_a) rem unsigned(operand_b));
                            end if;

                        when others =>
                            null;
                    end case;
                else
                    case funct3 is
                        when "000" =>
                            if funct7 = "0000000" then
                                result_value := std_logic_vector(
                                    unsigned(operand_a) + unsigned(operand_b));
                            elsif funct7 = "0100000" then
                                result_value := std_logic_vector(
                                    unsigned(operand_a) - unsigned(operand_b));
                            end if;

                        when "001" =>
                            if funct7 = "0000000" then
                                result_value := std_logic_vector(
                                    shift_left(unsigned(operand_a), shift_amount));
                            end if;

                        when "010" =>
                            if funct7 = "0000000" and
                               signed(operand_a) < signed(operand_b) then
                                result_value := x"00000001";
                            elsif funct7 = "0000000" then
                                result_value := x"00000000";
                            end if;

                        when "011" =>
                            if funct7 = "0000000" and
                               unsigned(operand_a) < unsigned(operand_b) then
                                result_value := x"00000001";
                            elsif funct7 = "0000000" then
                                result_value := x"00000000";
                            end if;

                        when "100" =>
                            if funct7 = "0000000" then
                                result_value := operand_a xor operand_b;
                            end if;

                        when "101" =>
                            if funct7 = "0000000" then
                                result_value := std_logic_vector(
                                    shift_right(unsigned(operand_a), shift_amount));
                            elsif funct7 = "0100000" then
                                result_value := std_logic_vector(
                                    shift_right(signed(operand_a), shift_amount));
                            end if;

                        when "110" =>
                            if funct7 = "0000000" then
                                result_value := operand_a or operand_b;
                            end if;

                        when "111" =>
                            if funct7 = "0000000" then
                                result_value := operand_a and operand_b;
                            end if;

                        when others =>
                            null;
                    end case;
                end if;

            when "0010011" =>
                case funct3 is
                    when "000" =>
                        result_value := std_logic_vector(
                            unsigned(operand_a) + unsigned(operand_b));

                    when "001" =>
                        if funct7 = "0000000" then
                            result_value := std_logic_vector(
                                shift_left(unsigned(operand_a), shift_amount));
                        end if;

                    when "010" =>
                        if signed(operand_a) < signed(operand_b) then
                            result_value := x"00000001";
                        end if;

                    when "011" =>
                        if unsigned(operand_a) < unsigned(operand_b) then
                            result_value := x"00000001";
                        end if;

                    when "100" =>
                        result_value := operand_a xor operand_b;

                    when "101" =>
                        if funct7 = "0000000" then
                            result_value := std_logic_vector(
                                shift_right(unsigned(operand_a), shift_amount));
                        elsif funct7 = "0100000" then
                            result_value := std_logic_vector(
                                shift_right(signed(operand_a), shift_amount));
                        end if;

                    when "110" =>
                        result_value := operand_a or operand_b;

                    when "111" =>
                        result_value := operand_a and operand_b;

                    when others =>
                        null;
                end case;

            when "1100011" =>
                case funct3 is
                    when "000" =>
                        if operand_a = operand_b then
                            branch_value := '1';
                        end if;

                    when "001" =>
                        if operand_a /= operand_b then
                            branch_value := '1';
                        end if;

                    when "100" =>
                        if signed(operand_a) < signed(operand_b) then
                            branch_value := '1';
                        end if;

                    when "101" =>
                        if signed(operand_a) >= signed(operand_b) then
                            branch_value := '1';
                        end if;

                    when "110" =>
                        if unsigned(operand_a) < unsigned(operand_b) then
                            branch_value := '1';
                        end if;

                    when "111" =>
                        if unsigned(operand_a) >= unsigned(operand_b) then
                            branch_value := '1';
                        end if;

                    when others =>
                        null;
                end case;

            when others =>
                null;
        end case;

        result <= result_value;
        branch_taken <= branch_value;
    end process;
end rtl;
