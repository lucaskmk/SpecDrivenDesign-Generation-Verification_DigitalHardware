# SpecHDL — imagem de toolchain do projeto (NFR-RV-05)
#
# Estende a imagem de referência da disciplina (rafaelcorsi/pl-descomp-cocotb,
# que já traz GHDL + cocotb, e é a mesma usada na CI do smoke test) com:
#   - binutils cruzado RISC-V (as/ld/objcopy/objdump) — o ORÁCULO do montador
#     Python: assembly -> ELF -> binário, conferido palavra a palavra contra
#     `rvverify/asm.py` em `rvverify/tests/test_assembler_oracle.py`
#   - Yosys — síntese e `stat` da análise de área (FR-RV-25, ADR-005)
#
# Objetivo: num clone limpo do repositório, montar e simular sem instalar
# nada na máquina host e sem caminho de toolchain hardcoded (contraste com
# cpus/rv32i_pipeline/compilation/Makefile, que ainda aponta pra um diretório
# xPack local, com .exe de Windows, que não está versionado). Ver
# specs/spec.md, NFR-RV-05, e specs/decisions.md, ADR-004 (Revisão).
#
# Esta imagem é OPCIONAL por definição: NFR-RV-05 exige que a ausência dela
# apenas pule a conferência, nunca reprove a suíte. O montador Python continua
# sendo o caminho autocontido.
#
# Build:
#   docker build -t spechdl-toolchain -f docker/Dockerfile docker
#
# Aceite (TRV-7.7.6):
#   docker run --rm spechdl-toolchain bash -lc "riscv64-unknown-elf-as --version; ghdl --version; yosys -V"
#   docker run --rm -v "${PWD}:/job" spechdl-toolchain make -C legado/toolchain_smoketest/test/

# Base pinada por digest (princípio 6 — reprodutibilidade). O digest abaixo
# corresponde a rafaelcorsi/pl-descomp-cocotb:latest em 2026-09-04
# (Debian 12 bookworm, GHDL 2.0.0 mcode, Python 3.11, cocotb 2.0.0).
# Para atualizar a base: sobrescreva via --build-arg BASE_IMAGE=...
ARG BASE_IMAGE=rafaelcorsi/pl-descomp-cocotb@sha256:8dc17254ed4b33be37c72759ba4ef4978e495b6efa668eb619e76c9f30b73a41
FROM ${BASE_IMAGE}

LABEL org.opencontainers.image.title="spechdl-toolchain" \
      org.opencontainers.image.description="GHDL + cocotb + RISC-V cross binutils + Yosys (SpecHDL, NFR-RV-05)" \
      org.opencontainers.image.source="https://github.com/lucaskmk/SpecDrivenDesign-Generation-Verification_DigitalHardware"

# Versões vindas do bookworm/main (fixadas para o build ser determinístico):
#   binutils-riscv64-unknown-elf 2.40  -> as/ld/objcopy/objdump com alvo rv32
#                                         via flags (-march=rv32i, -mabi=ilp32)
#   yosys                        0.23  -> síntese/`stat` da análise de área
# Só binutils: os programas de teste de CPU são escritos direto em assembly
# (ADR-004), então não há compilador C no caminho.
# ghdl-yosys-plugin (frontend VHDL do Yosys) não é pacote Debian; o caminho de
# síntese desta trilha usa `ghdl synth --out=verilog` alimentando o Yosys
# (ADR-005), então o plugin não é necessário aqui.
ARG RISCV_BINUTILS_VERSION=2.40-2+4+b1
ARG YOSYS_VERSION=0.23-6

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        "binutils-riscv64-unknown-elf=${RISCV_BINUTILS_VERSION}" \
        "yosys=${YOSYS_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

# Falha o build (em vez do teste do oráculo, muito depois) se algum dos
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
