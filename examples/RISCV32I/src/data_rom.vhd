-- Project      : simple_RISCV_RV32I_vhdl
-- Author       : Morgan Demange <https://github.com/MorganDemange>
-- Date         : August 4, 2024
-- File         : data_rom.vhd

-- Description  :   Read-only memory containing the program's constant data.
--
--                  This module provides 8-bit, 16-bit and 32-bit readings, which are asynchronous.
--                  This memory uses little-endian storing.
--                  It is byte-addressable, however accesses must be aligned to 16-bit boundaries for halfwords and to 32-bit boundaries
--                  for words.
--
--                  This memory is mapped from address DATA_MEMORY_BASE_ADDRESS to address (DATA_MEMORY_BASE_ADDRESS+DATA_ROM_MEMORY_SIZE_BYTES-1),
--                  both included.
--                  The input address (addr signal) is relative to the memory base address (DATA_MEMORY_BASE_ADDRESS).
--
--                  In case of an out-of range or unaligned access, the ouput reads 0xffffffff.
--
-- Modified     :   SpecHDL / trilha RISC-V -- REQ: FR-RV-06, FR-RV-07
--                  Same 2-D -> 1-D storage refactor as data_ram.vhd, for the same
--                  reason (the GHDL VPI does not expose 2-D arrays to cocotb).
--                  See specs/decisions.md, ADR-002. Externally visible behaviour
--                  is unchanged; enforced by examples/RISCV32I/test/test_memory.py.

library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
use IEEE.NUMERIC_STD.ALL;
use work.cpu_package.all;
use work.memory_package.all;


entity data_rom is
    port(
        addr            : in std_logic_vector(31 downto 0);
        access_width    : in MEM_ACCESS_WIDTH_t;

        data            : out std_logic_vector(31 downto 0)
    );
end data_rom;


architecture Behavioral of data_rom is
    signal memory       : DATA_ROM_MEMORY_ARRAY_t := DATA_ROM_MEMORY_CONTENT;
    signal word_index   : integer := 0;

begin
    word_index <= to_integer(unsigned(addr(31 downto 2)));

    -- reading
    --
    -- NOTE: same constraint as data_ram.vhd -- the range guard and the array
    -- index must be evaluated in the same expression, or the guard lags the
    -- index by a delta cycle and an out-of-range address indexes the array.
    data <=
        -- forbidding out-of-range and unaligned access
        (others => '1')
            when word_index >= DATA_ROM_MEMORY_SIZE_WORDS
              or (access_width = MEM_ACCESS_WIDTH_16 and addr(0) = '1')
              or (access_width = MEM_ACCESS_WIDTH_32 and addr(1 downto 0) /= "00") else

        -- 16-bit
        (31 downto 16 => '0') & memory(word_index)(15 downto 0)
            when access_width = MEM_ACCESS_WIDTH_16 and addr(1) = '0' else
        (31 downto 16 => '0') & memory(word_index)(31 downto 16)
            when access_width = MEM_ACCESS_WIDTH_16 else

        -- 32-bit
        memory(word_index)
            when access_width = MEM_ACCESS_WIDTH_32 else

        -- 8-bit
        (31 downto 8 => '0') & memory(word_index)(7 downto 0)    when addr(1 downto 0) = "00" else
        (31 downto 8 => '0') & memory(word_index)(15 downto 8)   when addr(1 downto 0) = "01" else
        (31 downto 8 => '0') & memory(word_index)(23 downto 16)  when addr(1 downto 0) = "10" else
        (31 downto 8 => '0') & memory(word_index)(31 downto 24);

end Behavioral;
