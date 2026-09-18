# REQ: FR-RV-38 -- sem isto, o Fitter/TimeQuest nao tem clock pra otimizar
# nem pra medir, e qualquer Fmax reportado nao seria confiavel.
create_clock -name clk -period 10.000 [get_ports {clk}]
derive_clock_uncertainty
