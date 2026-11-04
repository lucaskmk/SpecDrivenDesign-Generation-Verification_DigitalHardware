# Ambiente completo do veredito do rvgen: GHDL + cocotb (imagem das aulas),
# compilador RISC-V e o riscv-tests oficial fixo num commit. O repositorio
# entra montado em /repo (nada do repositorio, nem o .env, e copiado para a imagem).
#
#   docker build -t rvgen-veredito docker/veredito
#
# Ver docker/veredito/README.md para os comandos de uso.
#
# Base fixa por digest, o mesmo de docker/spechdl-toolchain e
# docker/pl-descomp-cocotb: rafaelcorsi/pl-descomp-cocotb:latest publicada em
# 2025-09-29 (Debian 12, GHDL 2.0.0, cocotb 2.0.0, Python 3.11.2). Para trocar:
# --build-arg BASE_IMAGE=...
ARG BASE_IMAGE=rafaelcorsi/pl-descomp-cocotb@sha256:8dc17254ed4b33be37c72759ba4ef4978e495b6efa668eb619e76c9f30b73a41
FROM ${BASE_IMAGE}

# Compilador e binutils RISC-V fixos na versao do Debian 12 (bookworm) com que
# o veredito foi medido. Se o espelho do Debian deixar de ter a versao, o build
# falha em vez de trocar o compilador em silencio; passe outra versao por
# --build-arg. git e ca-certificates so baixam o riscv-tests e nao entram no
# veredito, por isso ficam sem versao fixa.
ARG RISCV_GCC_VERSION=12.2.0-14+deb12u1+11+b2
ARG RISCV_BINUTILS_VERSION=2.40-2+4+b1
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      "gcc-riscv64-unknown-elf=${RISCV_GCC_VERSION}" \
      "binutils-riscv64-unknown-elf=${RISCV_BINUTILS_VERSION}" \
      git ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# riscv-tests fixo: o veredito so e comparavel entre maquinas se os programas
# de teste forem os mesmos. O ambiente de link (env/, link-zero.ld) vem do
# proprio spec-riscv-test, entao o submodulo env do upstream nao e necessario.
ARG RISCV_TESTS_REPO=https://github.com/riscv-software-src/riscv-tests
ARG RISCV_TESTS_COMMIT=3df703cd52d5f0d8224e3c50bf03c6cb70efff98
RUN git init -q /opt/riscv-tests \
 && git -C /opt/riscv-tests remote add origin "$RISCV_TESTS_REPO" \
 && git -C /opt/riscv-tests fetch -q --depth 1 origin "$RISCV_TESTS_COMMIT" \
 && git -C /opt/riscv-tests checkout -q FETCH_HEAD \
 && test "$(git -C /opt/riscv-tests rev-parse HEAD)" = "$RISCV_TESTS_COMMIT" \
 && test -d /opt/riscv-tests/isa/rv32ui \
 && git -C /opt/riscv-tests log -1 --format='riscv-tests %H %cs' > /opt/riscv-tests.versao

# O spec-riscv-test roda direto do codigo do repositorio montado (o rvgen
# confere o hash dele), entao a imagem so guarda um wrapper.
RUN printf '%s\n' \
      '#!/bin/sh' \
      'export PYTHONPATH=/repo/spec-riscv-test${PYTHONPATH:+:$PYTHONPATH}' \
      'exec python3 -m spec_riscv_test.cli "$@"' \
      > /usr/local/bin/spec-riscv-test \
 && chmod +x /usr/local/bin/spec-riscv-test

ENV RVGEN_SPEC_RISCV_TEST=/usr/local/bin/spec-riscv-test \
    RVGEN_RISCV_TESTS=/opt/riscv-tests \
    PYTHONDONTWRITEBYTECODE=1
WORKDIR /repo
