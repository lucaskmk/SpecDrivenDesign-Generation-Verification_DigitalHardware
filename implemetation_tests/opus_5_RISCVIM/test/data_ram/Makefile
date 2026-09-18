TOPLEVEL_LANG = vhdl
TOPLEVEL = data_ram
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/data_ram.vhd
MODULE = test_data_ram

SIM = ghdl
SIM_ARGS = --vcd=data_ram.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
