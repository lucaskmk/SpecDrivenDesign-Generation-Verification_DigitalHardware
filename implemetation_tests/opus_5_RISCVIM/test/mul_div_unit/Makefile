TOPLEVEL_LANG = vhdl
TOPLEVEL = mul_div_unit
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/mul_div_unit.vhd
MODULE = test_mul_div_unit

SIM = ghdl
SIM_ARGS = --vcd=mul_div_unit.vcd

include $(shell cocotb-config --makefiles)/Makefile.sim
