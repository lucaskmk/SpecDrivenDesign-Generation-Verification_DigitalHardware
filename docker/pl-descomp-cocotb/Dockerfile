# Espelho, sem nenhuma modificação, da imagem de referência da disciplina
# (rafaelcorsi/pl-descomp-cocotb: Debian 12, GHDL 2.0.0 mcode, Python 3.11,
# cocotb 2.0.0), no mesmo digest em que docker/spechdl-toolchain/ a pina.
# Publicada como gabrielgalazzi/imagens_projeto_descomp:cocotb-latest para que
# a base continue disponível mesmo se a original sumir ou mudar de digest
# (princípio 6 — reprodutibilidade). Ver docker/README.md e ADR-017.
#
# Só FROM, de propósito: o build devolve a própria imagem base, com o mesmo
# ID. Qualquer coisa acrescentada aqui deixaria de ser um espelho.
#
# Build:
#   docker build -t pl-descomp-cocotb docker/pl-descomp-cocotb
ARG BASE_IMAGE=rafaelcorsi/pl-descomp-cocotb@sha256:8dc17254ed4b33be37c72759ba4ef4978e495b6efa668eb619e76c9f30b73a41
FROM ${BASE_IMAGE}
