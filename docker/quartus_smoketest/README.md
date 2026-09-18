# Smoke test do fluxo Quartus (RV-8)

Projeto mínimo — um contador de 4 bits (`counter4.vhd`), não a CPU — usado
pra provar que a imagem `quartus-lite:25.1` (`docker/Quartus_Dockerfile`,
ADR-015) builda **e** compila de verdade contra o device alvo deste
projeto, `5CEBA4F23C7` (Cyclone V), antes de apontar o fluxo pra
`cpus/rv32i_pipeline` inteiro, que é bem mais pesado. Ver `specs/tasks.md`,
TRV-8.3, e `specs/decisions.md`, ADR-016 (o `5CEBA4F23C7` correto só foi
confirmado depois que a primeira tentativa, contra `5CEBA4F23C7N`, reprovou
de verdade).

## Rodar

Da raiz do repositório:

```
docker run --rm -v "$PWD/docker/quartus_smoketest:/workspace" \
    quartus-lite:25.1 --flow compile counter4
```

Saída esperada: `Quartus Prime Full Compilation was successful` com exit
code 0. Os avisos de timing ("Timing requirements not met") são esperados
neste smoke test — não há `.sdc` ainda (`TRV-8.4` adiciona um e mede timing
de verdade). Relatórios ficam em `output_files/` (gitignored — são
artefato, não fonte); `output_files/counter4.fit.summary` traz a utilização
de recursos real.

`list_parts.tcl` é um utilitário separado, não parte do smoke test em si:
lista os devices Cyclone V de verdade instalados na imagem, pra reconferir
a string exata de um device antes de fixá-la em qualquer `.qsf` (ver
ADR-016 sobre por que isso importa).

```
docker run --rm -v "$PWD/docker/quartus_smoketest:/workspace" \
    quartus-lite:25.1 -t list_parts.tcl
```
