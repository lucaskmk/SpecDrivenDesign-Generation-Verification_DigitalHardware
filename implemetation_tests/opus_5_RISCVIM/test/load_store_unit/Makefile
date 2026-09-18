TOPLEVEL_LANG = vhdl
TOPLEVEL = load_store_unit
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/load_store_unit.vhd
MODULE = test_load_store_unit

SIM = ghdl
SIM_ARGS = --vcd=load_store_unit.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
