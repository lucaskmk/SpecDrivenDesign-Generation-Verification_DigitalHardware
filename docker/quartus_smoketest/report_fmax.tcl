# REQ: FR-RV-38 -- Fmax nao sai do relatorio padrao de --flow compile
# (confirmado por execucao: counter4.sta.rpt nao tem secao Fmax), precisa
# desta chamada explicita da API do TimeQuest. O nome certo do comando e
# report_clock_fmax_summary, nao report_fmax_summary (confirmado lendo
# common/tcl/internal/init/sta.cmds.hlp dentro da propria imagem).
project_open counter4 -revision counter4
create_timing_netlist
read_sdc
update_timing_netlist
report_clock_fmax_summary -panel_name Fmax -stdout
