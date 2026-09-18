# Assinalamentos comuns as quatro revisoes (rv32i, rv32im e as duas _a9). Ficam num unico
# arquivo de proposito: a comparacao A/B da extensao M so vale se a UNICA
# diferenca entre duas compilacoes comparaveis seja o generic RV32M_ENABLE.
#
# REQ: FR-15 (A/B da extensao M), NFR-01, NFR-02, NFR-03
# REQ (repositorio): repo:FR-RV-36, repo:FR-RV-38, repo:FR-RV-41, ADR-015

# FAMILY e DEVICE NAO ficam aqui: sao a unica coisa que muda entre o alvo
# default do projeto (5CEBA4F23C7, FR-RV-37) e o device maior usado so para
# medir timing e potencia depois que o alvo default REPROVOU por area. Cada
# .qsf declara o seu; tudo o mais e identico por construcao.
set_global_assignment -name TOP_LEVEL_ENTITY cpu
set_global_assignment -name ORIGINAL_QUARTUS_VERSION 25.1STD.0
set_global_assignment -name LAST_QUARTUS_VERSION "25.1STD.0 Lite Edition"
set_global_assignment -name PROJECT_OUTPUT_DIRECTORY output_files
set_global_assignment -name MIN_CORE_JUNCTION_TEMP 0
set_global_assignment -name MAX_CORE_JUNCTION_TEMP 85
set_global_assignment -name ERROR_CHECK_FREQUENCY_DIVISOR 1
set_global_assignment -name VHDL_INPUT_VERSION VHDL_2008
set_global_assignment -name VHDL_SHOW_LMF_MAPPING_MESSAGES OFF

# MESMA ordem de analise de cpu.toml: em VHDL um pacote vem antes de quem o usa.
set_global_assignment -name VHDL_FILE ../src/cpu_pkg.vhd
set_global_assignment -name VHDL_FILE ../software/riscv_base_test/rom_image_pkg.vhd
set_global_assignment -name VHDL_FILE ../src/program_counter.vhd
set_global_assignment -name VHDL_FILE ../src/instruction_rom.vhd
set_global_assignment -name VHDL_FILE ../src/data_ram.vhd
set_global_assignment -name VHDL_FILE ../src/register_file.vhd
set_global_assignment -name VHDL_FILE ../src/immediate_generator.vhd
set_global_assignment -name VHDL_FILE ../src/alu.vhd
set_global_assignment -name VHDL_FILE ../src/mul_div_unit.vhd
set_global_assignment -name VHDL_FILE ../src/branch_unit.vhd
set_global_assignment -name VHDL_FILE ../src/load_store_unit.vhd
set_global_assignment -name VHDL_FILE ../src/control_unit.vhd
set_global_assignment -name VHDL_FILE ../src/cpu.vhd

set_global_assignment -name SDC_FILE rv32im_sc.sdc
