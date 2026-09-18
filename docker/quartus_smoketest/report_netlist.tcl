# REQ: FR-RV-40 -- prova de que os dados de netlist (nao uma imagem) sao
# acessiveis sem GUI, via ::quartus::rtl, mesmo sem export headless de
# PNG/SVG/PDF do RTL Viewer (nenhum comando desse tipo existe nesta
# instalacao -- confirmado buscando em common/tcl/internal/init/*.hlp).
project_open counter4 -revision counter4
load_rtl_netlist
set cells [get_rtl_cells *]
puts "CELL_COUNT=[llength $cells]"
foreach c $cells { puts "  cell: $c" }
unload_rtl_netlist
