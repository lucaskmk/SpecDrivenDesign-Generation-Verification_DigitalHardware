TOPLEVEL_LANG = vhdl
TOPLEVEL = immediate_generator
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/immediate_generator.vhd
MODULE = test_immediate_generator

SIM = ghdl
SIM_ARGS = --vcd=immediate_generator.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
