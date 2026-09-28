# Imagens Docker

Uma pasta por imagem (ADR-017). Cada pasta é o build context da imagem de
mesmo nome e corresponde a uma tag publicada no Docker Hub, em
[`gabrielgalazzi/imagens_projeto_descomp`](https://hub.docker.com/r/gabrielgalazzi/imagens_projeto_descomp).

| pasta | imagem local | tag publicada | o que é |
|---|---|---|---|
| [`pl-descomp-cocotb/`](pl-descomp-cocotb/Dockerfile) | `pl-descomp-cocotb` | `cocotb-latest` | Espelho, sem modificação, da imagem de referência da disciplina (GHDL + cocotb). É a base da `spechdl-toolchain`. |
| [`spechdl-toolchain/`](spechdl-toolchain/Dockerfile) | `spechdl-toolchain` | `spechdl-latest` | Oráculo opcional do montador (NFR-RV-05): a base acima + binutils RISC-V + Yosys. Sem ela, `rvverify` roda igual. |
| [`quartus-lite/`](quartus-lite/Dockerfile) | `quartus-lite:25.1` | `25.1` | Quartus Prime Lite para a análise de FPGA da RV-8 (NFR-RV-06). Separada para sempre das outras duas (ADR-015). |

Digests publicados (conferidos no Docker Hub em 2026-09-28; mudam a cada
`push` novo):

```
cocotb-latest   sha256:8dc17254ed4b33be37c72759ba4ef4978e495b6efa668eb619e76c9f30b73a41
spechdl-latest  sha256:76f770e2c43fc23d837cd6b63765b8a59caae8847819e7129439c218418aac07
25.1            sha256:34aa0419b1b93528bcd1cf08cef1ba698fc1ca0408a558f9e11253c2b7f5cd33
```

## Buildar

Da raiz do repositório, sempre `docker build -t <imagem local> docker/<pasta>`:

```
docker build -t pl-descomp-cocotb docker/pl-descomp-cocotb
docker build -t spechdl-toolchain docker/spechdl-toolchain
docker build -t quartus-lite:25.1 docker/quartus-lite
```

A do Quartus só builda com o instalador baixado à mão em
[`quartus-lite/quartus_installers/`](quartus-lite/quartus_installers/README.md).

## Puxar em vez de buildar

O código do projeto usa os nomes locais. Para usar a versão publicada, puxe e
dê a ela o nome local:

```
docker pull gabrielgalazzi/imagens_projeto_descomp:spechdl-latest
docker tag  gabrielgalazzi/imagens_projeto_descomp:spechdl-latest spechdl-toolchain
```

(o mesmo com `25.1` -> `quartus-lite:25.1` e `cocotb-latest` ->
`pl-descomp-cocotb`).

## Publicar uma versão nova

```
docker tag  spechdl-toolchain gabrielgalazzi/imagens_projeto_descomp:spechdl-latest
docker push gabrielgalazzi/imagens_projeto_descomp:spechdl-latest
```

Depois de um `push`, atualize o digest na lista acima.
