library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity alu is
    port(
        operand_a : in  std_logic_vector(31 downto 0);
        operand_b : in  std_logic_vector(31 downto 0);
        opcode    : in  std_logic_vector(6 downto 0);
        funct3    : in  std_logic_vector(2 downto 0);
        funct7    : in  std_logic_vector(6 downto 0);
        result    : out std_logic_vector(31 downto 0)
    );
end alu;

architecture rtl of alu is
begin
    process(all)
        variable res          : std_logic_vector(31 downto 0);
        variable product_ss   : signed(63 downto 0);
        variable product_uu   : unsigned(63 downto 0);
        variable product_su   : signed(65 downto 0);
        variable extended_a  : signed(32 downto 0);
        variable extended_b  : signed(32 downto 0);
        variable shift_amount : natural range 0 to 31;
    begin
        res := (others => '0');
        shift_amount := to_integer(unsigned(operand_b(4 downto 0)));

        case opcode is
            when "0110011" =>
                if funct7 = "0000001" then
                    case funct3 is
                        when "000" =>
                            product_uu := unsigned(operand_a) * unsigned(operand_b);
                            res := std_logic_vector(product_uu(31 downto 0));
                        when "001" =>
                            product_ss := signed(operand_a) * signed(operand_b);
                            res := std_logic_vector(product_ss(63 downto 32));
                        when "010" =>
                            extended_a := resize(signed(operand_a), 33);
                            extended_b := signed('0' & operand_b);
                            product_su := extended_a * extended_b;
                            res := std_logic_vector(product_su(63 downto 32));
                        when "011" =>
                            product_uu := unsigned(operand_a) * unsigned(operand_b);
                            res := std_logic_vector(product_uu(63 downto 32));
                        when "100" =>
                            if operand_b = x"00000000" then
                                res := (others => '1');
                            elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                                res := x"80000000";
                            else
                                res := std_logic_vector(signed(operand_a) / signed(operand_b));
                            end if;
                        when "101" =>
                            if operand_b = x"00000000" then
                                res := (others => '1');
                            else
                                res := std_logic_vector(unsigned(operand_a) / unsigned(operand_b));
                            end if;
                        when "110" =>
                            if operand_b = x"00000000" then
                                res := operand_a;
                            elsif operand_a = x"80000000" and operand_b = x"FFFFFFFF" then
                                res := x"00000000";
                            else
                                res := std_logic_vector(signed(operand_a) rem signed(operand_b));
                            end if;
                        when "111" =>
                            if operand_b = x"00000000" then
                                res := operand_a;
                            else
                                res := std_logic_vector(unsigned(operand_a) rem unsigned(operand_b));
                            end if;
                        when others =>
                            null;
                    end case;
                else
                    case funct3 is
                        when "000" =>
                            if funct7 = "0000000" then
                                res := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));
                            elsif funct7 = "0100000" then
                                res := std_logic_vector(unsigned(operand_a) - unsigned(operand_b));
                            end if;
                        when "001" =>
                            if funct7 = "0000000" then
                                res := std_logic_vector(shift_left(unsigned(operand_a), shift_amount));
                            end if;
                        when "010" =>
                            if funct7 = "0000000" and signed(operand_a) < signed(operand_b) then
                                res := x"00000001";
                            end if;
                        when "011" =>
                            if funct7 = "0000000" and unsigned(operand_a) < unsigned(operand_b) then
                                res := x"00000001";
                            end if;
                        when "100" =>
                            if funct7 = "0000000" then
                                res := operand_a xor operand_b;
                            end if;
                        when "101" =>
                            if funct7 = "0000000" then
                                res := std_logic_vector(shift_right(unsigned(operand_a), shift_amount));
                            elsif funct7 = "0100000" then
                                res := std_logic_vector(shift_right(signed(operand_a), shift_amount));
                            end if;
                        when "110" =>
                            if funct7 = "0000000" then
                                res := operand_a or operand_b;
                            end if;
                        when "111" =>
                            if funct7 = "0000000" then
                                res := operand_a and operand_b;
                            end if;
                        when others =>
                            null;
                    end case;
                end if;

            when "0010011" =>
                case funct3 is
                    when "000" =>
                        res := std_logic_vector(unsigned(operand_a) + unsigned(operand_b));
                    when "001" =>
                        if funct7 = "0000000" then
                            res := std_logic_vector(shift_left(unsigned(operand_a), shift_amount));
                        end if;
                    when "010" =>
                        if signed(operand_a) < signed(operand_b) then
                            res := x"00000001";
                        end if;
                    when "011" =>
                        if unsigned(operand_a) < unsigned(operand_b) then
                            res := x"00000001";
                        end if;
                    when "100" =>
                        res := operand_a xor operand_b;
                    when "101" =>
                        if funct7 = "0000000" then
                            res := std_logic_vector(shift_right(unsigned(operand_a), shift_amount));
                        elsif funct7 = "0100000" then
                            res := std_logic_vector(shift_right(signed(operand_a), shift_amount));
                        end if;
                    when "110" =>
                        res := operand_a or operand_b;
                    when "111" =>
                        res := operand_a and operand_b;
                    when others =>
                        null;
                end case;

            when others =>
                null;
        end case;

        result <= res;
    end process;
end rtl;
