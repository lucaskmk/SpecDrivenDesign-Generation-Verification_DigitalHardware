TOPLEVEL_LANG = vhdl
TOPLEVEL = register_file
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/register_file.vhd
MODULE = test_register_file

SIM = ghdl
SIM_ARGS = --vcd=register_file.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
