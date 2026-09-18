TOPLEVEL_LANG = vhdl
TOPLEVEL = control_unit
VHDL_SOURCES = ../../src/cpu_pkg.vhd ../../src/control_unit.vhd
MODULE = test_control_unit

SIM = ghdl
SIM_ARGS = --vcd=control_unit.vcd

PYTHONPATH := $(shell pwd)/../lib:$(PYTHONPATH)
export PYTHONPATH

include $(shell cocotb-config --makefiles)/Makefile.sim
