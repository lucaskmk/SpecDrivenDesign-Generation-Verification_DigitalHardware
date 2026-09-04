# SpecHDL — imagem de toolchain do projeto (NFR-05, T0.6)
#
# Estende a imagem de referência da disciplina (rafaelcorsi/pl-descomp-cocotb,
# que já traz GHDL + cocotb, e é a mesma usada na CI do smoke test) com:
#   - binutils cruzado RISC-V (as/ld/objcopy/objdump) — fase 3b: assembly ->
#     ELF -> binário -> .rm
#   - Yosys — fase 5 (análise PPA)
#
# Objetivo: num clone limpo do repositório, montar e simular sem instalar
# nada na máquina host e sem caminho de toolchain hardcoded (contraste com
# examples/RISCV32I/compilation/Makefile, que aponta pra um diretório xPack
# local que não está versionado). Ver specs/plan.md, "Toolchain de CPU —
# imagem única, sem instalação manual (NFR-05)".
#
# Build:
#   docker build -t spechdl-toolchain -f docker/Dockerfile docker
#
# Aceite (T0.6):
#   docker run --rm spechdl-toolchain bash -lc "riscv64-unknown-elf-as --version; ghdl --version; yosys -V"
#   docker run --rm -v "${PWD}:/job" spechdl-toolchain make -C examples/toolchain_smoketest/test/

# Base pinada por digest (princípio 6 — reprodutibilidade). O digest abaixo
# corresponde a rafaelcorsi/pl-descomp-cocotb:latest em 2026-09-04
# (Debian 12 bookworm, GHDL 2.0.0 mcode, Python 3.11, cocotb 2.0.0).
# Para atualizar a base: sobrescreva via --build-arg BASE_IMAGE=...
ARG BASE_IMAGE=rafaelcorsi/pl-descomp-cocotb@sha256:8dc17254ed4b33be37c72759ba4ef4978e495b6efa668eb619e76c9f30b73a41
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="spechdl-toolchain" \
      org.opencontainers.image.description="GHDL + cocotb + RISC-V cross binutils + Yosys (SpecHDL, NFR-05)" \
      org.opencontainers.image.source="https://github.com/lucaskmk/SpecDrivenDesign-Generation-Verification_DigitalHardware"

# Versões vindas do bookworm/main (fixadas para o build ser determinístico):
#   binutils-riscv64-unknown-elf 2.40  -> as/ld/objcopy/objdump com alvo rv32
#                                         via flags (-march=rv32i, -mabi=ilp32)
#   yosys                        0.23  -> síntese/`stat` da fase 5
# Só binutils: os programas de teste de CPU são escritos direto em assembly
# (specs/plan.md, fase 3b), então não há compilador C no caminho.
# ghdl-yosys-plugin (frontend VHDL do Yosys) não é pacote Debian e fica para
# o T0.3, que decide entre build do plugin e o fallback heurístico do FR-14.
ARG RISCV_BINUTILS_VERSION=2.40-2+4+b1
ARG YOSYS_VERSION=0.23-6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        "binutils-riscv64-unknown-elf=${RISCV_BINUTILS_VERSION}" \
        "yosys=${YOSYS_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

# Falha o build (em vez da fase 3b/5, muito depois) se algum dos três
# executáveis não responder.
RUN riscv64-unknown-elf-as --version > /dev/null \
    && riscv64-unknown-elf-ld --version > /dev/null \
    && riscv64-unknown-elf-objcopy --version > /dev/null \
    && riscv64-unknown-elf-objdump --version > /dev/null \
    && ghdl --version > /dev/null \
    && yosys -V > /dev/null

# /job é o workdir da imagem base; o repositório é montado aqui
# (docker run -v "${PWD}:/job").
WORKDIR /job
