TOPLEVEL_LANG = vhdl
TOPLEVEL = alu
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/alu.vhd
MODULE = test_alu

SIM = ghdl
SIM_ARGS = --vcd=alu.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
