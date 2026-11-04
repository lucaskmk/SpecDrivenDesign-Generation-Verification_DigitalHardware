# Smoke test do fluxo Quartus

Projeto mínimo — um contador de 4 bits (`counter4.vhd`), não a CPU — usado
pra provar que a imagem `quartus-lite:25.1` (`docker/quartus-lite/Dockerfile`,
builda **e** compila de verdade contra o device alvo deste
projeto, `5CEBA4F23C7` (Cyclone V), antes de apontar o fluxo pra
`cpus/rv32i_pipeline` inteiro, que é bem mais pesado. O `5CEBA4F23C7`
correto só foi confirmado depois que a primeira tentativa, contra
`5CEBA4F23C7N`, reprovou de verdade.

## Rodar

Da raiz do repositório:

```
docker run --rm -v "$PWD/docker/quartus-lite/quartus_smoketest:/workspace" \
    quartus-lite:25.1 --flow compile counter4
```

Saída esperada: `Quartus Prime Full Compilation was successful` com exit
code 0. Os avisos de timing ("Timing requirements not met") são esperados
neste smoke test — a restrição de clock e a leitura de timing estão em
*Timing real*, abaixo. Relatórios ficam em `output_files/` (gitignored — são
artefato, não fonte); `output_files/counter4.fit.summary` traz a utilização
de recursos real.

`list_parts.tcl` é um utilitário separado, não parte do smoke test em si:
lista os devices Cyclone V de verdade instalados na imagem, pra reconferir
a string exata de um device antes de fixá-la em qualquer `.qsf` (ver o
primeiro parágrafo sobre por que isso importa).

```
docker run --rm -v "$PWD/docker/quartus-lite/quartus_smoketest:/workspace" \
    quartus-lite:25.1 -t list_parts.tcl
```

## Timing real

`counter4.sdc` restringe `clk` a 100 MHz (`create_clock -period 10.000`).
Sem ele, o `--flow compile` acima roda igual, mas com um clock de 1 ns
inventado pelo Quartus (`derive_clocks -period 1.0`) e um aviso explícito de
que faltou o `.sdc` — qualquer Fmax lido desse cenário não significa nada.
Slack de setup/hold sai do relatório padrão
(`output_files/counter4.sta.summary`); Fmax **não** sai dele — precisa da
API do TimeQuest, só disponível em `quartus_sta`/`quartus_fit`, não em
`quartus_sh` (o `ENTRYPOINT` da imagem):

```
docker run --rm -v "$PWD/docker/quartus-lite/quartus_smoketest:/workspace" \
    --entrypoint quartus_sta quartus-lite:25.1 -t report_fmax.tcl
```

## Potência

```
docker run --rm -v "$PWD/docker/quartus-lite/quartus_smoketest:/workspace" \
    --entrypoint quartus_pow quartus-lite:25.1 counter4 -c counter4
```

`output_files/counter4.pow.summary` traz estática, dinâmica, de E/S e
total — o próprio Quartus já rotula a confiança da estimativa (baixa aqui,
por faltar dado de toggle rate de uma simulação real).

## Wrapper `analyze`

`docker/quartus-lite/quartus_analyzer/analyze.py` faz tudo isto num comando só —
compila, extrai fit/timing/Fmax/potência, grava
`quartus_output/{compilation,reports,netlist,bitstream}/` e
`quartus_output/reports/summary.json`:

```
docker run --rm -v "$PWD/docker/quartus-lite/quartus_smoketest:/workspace" \
    quartus-lite:25.1 analyze --project counter4
```

Sem `--revision`, usa o mesmo nome de `--project`. Uma falha de compilação
(projeto inexistente, erro de síntese) para no primeiro passo, grava
`compilation.success: false` em `summary.json` e sai com exit code
diferente de zero, sem tentar timing/potência sobre uma compilação
inválida.

## Netlist sem GUI

Não há exportação headless de PNG/SVG/PDF do RTL Viewer nesta instalação
(nenhum comando do tipo existe no banco de ajuda Tcl da imagem — conferido
por busca real, não suposição). Os **dados** de netlist continuam
acessíveis sem GUI via `::quartus::rtl`:

```
docker run --rm -v "$PWD/docker/quartus-lite/quartus_smoketest:/workspace" \
    --entrypoint quartus_map quartus-lite:25.1 -t report_netlist.tcl
```
