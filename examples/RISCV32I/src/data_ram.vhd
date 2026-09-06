-- Project      : simple_RISCV_RV32I_vhdl
-- Author       : Morgan Demange <https://github.com/MorganDemange>
-- Date         : July 28, 2024
-- File         : data_ram.vhd

-- Description  :   RAM part of the data memory.
--
--                  This module provides 8-bit, 16-bit and 32-bit accesses for readings as well as for writings.
--                  Readings are asynchronous, writings are synchronous and occur on clock rising edges.
--                  This memory uses little-endian storing.
--                  It is byte-addressable, however accesses must be aligned to 16-bit boundaries for halfwords and to 32-bit boundaries
--                  for words.
--
--                  The memory is mapped from address DATA_RAM_BASE_ADDRESS to address (DATA_RAM_BASE_ADDRESS+DATA_RAM_MEMORY_SIZE_BYTES-1),
--                  both included.
--                  The input address (addr signal) is relative to the memory base address (DATA_RAM_BASE_ADDRESS).
--
--                  In case of an out-of range or unaligned access, the ouput reads 0xffffffff and any writing is discarded.
--
-- Modified     :   SpecHDL / trilha RISC-V -- REQ: FR-RV-06, FR-RV-07
--
--                  The storage array was changed from
--                      array (0 to N-1, 3 downto 0) of std_logic_vector(7 downto 0)   -- 2-D, one element per byte
--                  to
--                      array (0 to N-1) of std_logic_vector(31 downto 0)              -- 1-D, one element per word
--                  because the GHDL VPI does not expose 2-D arrays, so the cocotb
--                  testbench could not read results back from the RAM
--                  (see specs/decisions.md, ADR-002).
--
--                  Byte and halfword accesses became word slices. The externally
--                  visible behaviour -- little-endian layout, alignment rules,
--                  0xffffffff on an out-of-range or unaligned read, silently
--                  discarded writes -- is unchanged, and that claim is enforced by
--                  examples/RISCV32I/test/test_memory.py.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;
use work.memory_package.all;


entity data_ram is
    port(
        clk             : in std_logic;
        addr            : in std_logic_vector(31 downto 0);
        access_width    : in MEM_ACCESS_WIDTH_t;
        write_enable    : in std_logic;
        data_in         : in std_logic_vector(31 downto 0);

        data_out        : out std_logic_vector(31 downto 0)
    );
end data_ram;


architecture Behavioral of data_ram is
    signal memory       : DATA_RAM_MEMORY_ARRAY_t := (others => (others => '0'));
    signal word_index   : integer := 0;

begin

    word_index <= to_integer(unsigned(addr(31 downto 2)));

    -- reading
    --
    -- NOTE: the range guard and the array index MUST stay inside the same
    -- conditional expression, exactly as in the original design. Splitting the
    -- guard into its own signal makes it lag `word_index` by one delta cycle,
    -- and an out-of-range address then indexes the array before the guard
    -- catches up (observed as "index out of bounds" under GHDL).
    data_out <=
        -- forbidding out-of-range and unaligned access
        (others => '1')
            when word_index >= DATA_RAM_MEMORY_SIZE_WORDS
              or (access_width = MEM_ACCESS_WIDTH_16 and addr(0) = '1')
              or (access_width = MEM_ACCESS_WIDTH_32 and addr(1 downto 0) /= "00") else

        -- 16-bit, zero-extended (sign extension is done by extend_32.vhd)
        (31 downto 16 => '0') & memory(word_index)(15 downto 0)
            when access_width = MEM_ACCESS_WIDTH_16 and addr(1) = '0' else
        (31 downto 16 => '0') & memory(word_index)(31 downto 16)
            when access_width = MEM_ACCESS_WIDTH_16 else

        -- 32-bit
        memory(word_index)
            when access_width = MEM_ACCESS_WIDTH_32 else

        -- 8-bit, zero-extended
        (31 downto 8 => '0') & memory(word_index)(7 downto 0)    when addr(1 downto 0) = "00" else
        (31 downto 8 => '0') & memory(word_index)(15 downto 8)   when addr(1 downto 0) = "01" else
        (31 downto 8 => '0') & memory(word_index)(23 downto 16)  when addr(1 downto 0) = "10" else
        (31 downto 8 => '0') & memory(word_index)(31 downto 24);


    -- writing
    process(clk)
        variable w : std_logic_vector(31 downto 0);
    begin
        if rising_edge(clk) then
            if word_index < DATA_RAM_MEMORY_SIZE_WORDS and write_enable = '1' then
                w := memory(word_index);
                case access_width is
                    when MEM_ACCESS_WIDTH_16 =>     -- 16-bit
                        -- forbidding unaligned access
                        if addr(0) = '0' then
                            if addr(1) = '0' then
                                w(15 downto 0)  := data_in(15 downto 0);
                            else
                                w(31 downto 16) := data_in(15 downto 0);
                            end if;
                            memory(word_index) <= w;
                        end if;

                    when MEM_ACCESS_WIDTH_32 =>     -- 32-bit
                        -- forbidding unaligned access
                        if addr(1 downto 0) = "00" then
                            memory(word_index) <= data_in;
                        end if;

                    when others =>                  -- 8-bit
                        case addr(1 downto 0) is
                            when "00"   => w(7 downto 0)   := data_in(7 downto 0);
                            when "01"   => w(15 downto 8)  := data_in(7 downto 0);
                            when "10"   => w(23 downto 16) := data_in(7 downto 0);
                            when others => w(31 downto 24) := data_in(7 downto 0);
                        end case;
                        memory(word_index) <= w;
                end case;
            end if;
        end if;

    end process;


end Behavioral;
