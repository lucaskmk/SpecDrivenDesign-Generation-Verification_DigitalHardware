# REQ: NFR-02 (alvo de 50 MHz) -- repo:FR-RV-38
# 20 ns e o mesmo periodo declarado em cpu.toml ([clock] period_ns = 20).
# Sem esta restricao o Quartus inventa um clock de 1 ns e qualquer Fmax lido
# nao significaria nada.
create_clock -name clk -period 20.000 [get_ports {clk}]
derive_clock_uncertainty

# rst e os dbg_* nao sao caminhos de I/O reais deste experimento: a analise
# aqui e do caminho interno de dados, nao de uma placa. Sem isto o TimeQuest
# reporta caminhos de I/O sem restricao junto com o caminho critico do nucleo.
set_false_path -from [get_ports {rst}] -to *
set_false_path -from * -to [get_ports {dbg_*}]
