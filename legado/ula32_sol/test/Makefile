TOPLEVEL_LANG = vhdl
SIM ?= ghdl

VHDL_SOURCES = $(PWD)/../src/ula32.vhd
TOPLEVEL = ula32
COCOTB_TEST_MODULES = test_ula32

SIM_ARGS += --wave=$(PWD)/ula32.ghw

include $(shell cocotb-config --makefiles)/Makefile.sim
