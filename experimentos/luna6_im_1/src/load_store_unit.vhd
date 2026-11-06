library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

entity load_store_unit is
    port(
        instr : in std_logic_vector(31 downto 0);
        effective_address : in std_logic_vector(31 downto 0);
        store_data_in : in std_logic_vector(31 downto 0);
        data_read_data : in std_logic_vector(31 downto 0);
        data_addr : out std_logic_vector(31 downto 0);
        data_write : out std_logic;
        data_width : out std_logic_vector(1 downto 0);
        data_write_data : out std_logic_vector(31 downto 0);
        load_result : out std_logic_vector(31 downto 0)
    );
end load_store_unit;

architecture rtl of load_store_unit is
begin
    process(all)
        variable byte_value : std_logic_vector(7 downto 0);
        variable half_value : std_logic_vector(15 downto 0);
    begin
        data_addr <= effective_address;
        data_write <= '0';
        data_width <= "10";
        data_write_data <= (others => '0');
        load_result <= (others => '0');
        byte_value := (others => '0');
        half_value := (others => '0');

        case instr(6 downto 0) is
            when "0000011" =>
                case instr(14 downto 12) is
                    when "000" | "100" =>
                        data_width <= "00";
                        case effective_address(1 downto 0) is
                            when "00" => byte_value := data_read_data(7 downto 0);
                            when "01" => byte_value := data_read_data(15 downto 8);
                            when "10" => byte_value := data_read_data(23 downto 16);
                            when others => byte_value := data_read_data(31 downto 24);
                        end case;

                        if instr(14 downto 12) = "000" then
                            load_result <= std_logic_vector(resize(signed(byte_value), 32));
                        else
                            load_result <= std_logic_vector(resize(unsigned(byte_value), 32));
                        end if;

                    when "001" | "101" =>
                        data_width <= "01";
                        if effective_address(1) = '0' then
                            half_value := data_read_data(15 downto 0);
                        else
                            half_value := data_read_data(31 downto 16);
                        end if;

                        if instr(14 downto 12) = "001" then
                            load_result <= std_logic_vector(resize(signed(half_value), 32));
                        else
                            load_result <= std_logic_vector(resize(unsigned(half_value), 32));
                        end if;

                    when "010" =>
                        data_width <= "10";
                        load_result <= data_read_data;

                    when others =>
                        null;
                end case;

            when "0100011" =>
                case instr(14 downto 12) is
                    when "000" =>
                        data_width <= "00";
                        data_write <= '1';
                        data_write_data <= store_data_in;
                    when "001" =>
                        data_width <= "01";
                        data_write <= '1';
                        data_write_data <= store_data_in;
                    when "010" =>
                        data_width <= "10";
                        data_write <= '1';
                        data_write_data <= store_data_in;
                    when others =>
                        null;
                end case;

            when others =>
                null;
        end case;
    end process;
end rtl;
