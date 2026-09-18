TOPLEVEL_LANG = vhdl
TOPLEVEL = program_counter
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/program_counter.vhd
MODULE = test_program_counter

SIM = ghdl
SIM_ARGS = --vcd=program_counter.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
