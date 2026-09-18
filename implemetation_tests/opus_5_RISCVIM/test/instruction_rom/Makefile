TOPLEVEL_LANG = vhdl
TOPLEVEL = instruction_rom
# The ROM image package is a phase-3b artifact: it is generated from the golden
# program .rm by software/tools/rm_to_rom_pkg.py, never hand written (FR-13).
VHDL_SOURCES = \
	../../src/cpu_pkg.vhd \
	../../software/riscv_base_test/rom_image_pkg.vhd \
	../../src/instruction_rom.vhd
MODULE = test_instruction_rom

SIM = ghdl
SIM_ARGS = --vcd=instruction_rom.vcd

export RM_PATH = ../../software/riscv_base_test/program.rm

include $(shell cocotb-config --makefiles)/Makefile.sim
