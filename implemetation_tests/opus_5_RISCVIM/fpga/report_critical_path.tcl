# Caminho critico de setup (o pior, -npaths 1) da revisao passada em -rev.
# REQ: NFR-02 -- o Fmax sozinho diz QUANTO; isto diz ONDE. Sem apontar o
# caminho, "9,84 MHz" e um numero sem diagnostico.
#
#   docker run --rm -v "$PWD/implemetation_tests/opus_5_RISCVIM:/workspace" \
#       --entrypoint quartus_sta quartus-lite:25.1 \
#       -t fpga/report_critical_path.tcl -rev rv32im_a9
#
# Roda so sobre uma revisao ja compilada com sucesso: le o netlist de timing
# que o Fitter deixou, nao recompila nada.
set rev "rv32im_a9"
if {[lsearch $quartus(args) "-rev"] >= 0} {
    set rev [lindex $quartus(args) [expr {[lsearch $quartus(args) "-rev"] + 1}]]
}
project_open rv32im_sc -revision $rev
create_timing_netlist
read_sdc
update_timing_netlist
report_timing -setup -npaths 1 -detail path_only -panel_name "Critical" -stdout
