# Fase 5b — análise de FPGA real (Quartus)

Projeto Quartus da CPU `rv32im_sc`. Existe para responder as duas linhas que a
[fase 5](../ppa/) deixou em branco no [`RELATORIO.md`](../RELATORIO.md) —
**frequência máxima** e **potência** —, e para checar área na unidade em que um
FPGA de verdade cobra: ALM ocupada, não LUT4 estimada pelo Yosys.

Roda pela imagem [`docker/Quartus_Dockerfile`](../../../docker/Quartus_Dockerfile)
do repositório e pelo wrapper `analyze`
([`docker/quartus_analyzer/analyze.py`](../../../docker/quartus_analyzer/analyze.py),
`repo:FR-RV-41`). A análise é **aditiva**: ela roda depois da conformidade da
RV-7 e não altera o veredito dela (`repo:NFR-RV-06`).

## As seis revisões

Mesma árvore de fontes, mesmo `.sdc`, mesma base de assinalamentos globais
([`common.tcl`](common.tcl)). Só três coisas mudam entre revisões — o
generic, o device e o esforço de roteamento —, e cada `.qsf` declara as suas:

| revisão | `RV32M_ENABLE` | device | roteamento | resultado |
|---|---|---|---|---|
| `rv32i` | `false` | `5CEBA4F23C7` | default | **não cabe** — 128 % de ALM |
| `rv32im` | `true` | `5CEBA4F23C7` | default | **não cabe** — 129 % de ALM |
| `rv32i_a9` | `false` | `5CEFA9F23C7` | default | cabe (27 %) mas **não roteia** |
| `rv32im_a9` | `true` | `5CEFA9F23C7` | default | **completo**: fit + timing + potência |
| `rv32i_a9r` | `false` | `5CEFA9F23C7` | agressivo | **completo** — é o baseline comparável |
| `rv32im_a9r` | `true` | `5CEFA9F23C7` | agressivo | **completo** — o par A/B de `rv32i_a9r` |

As duas últimas existem porque `rv32i_a9` reprovou **por roteamento**, não por
área (`Critical Warning (188026)`, com só 27 % do device ocupado), e sem
baseline roteado não haveria com o que comparar a extensão M (princípio 9). A
opção ligada nelas é a que o próprio Quartus recomenda nessa mensagem —
`FITTER_AGGRESSIVE_ROUTABILITY_OPTIMIZATION`, opção de **ferramenta**, com o
RTL bit a bit idêntico. **Compare sempre `_a9r` com `_a9r`**: `rv32im_a9` e
`rv32i_a9r` têm configurações de fitter diferentes e não formam um A/B
honesto.

O baseline RV32I vem antes do RV32IM em cada família de execução
(constituição, princípio 9), exatamente como nas duas etapas do validador.

**Por que existe um device maior.** O alvo default reprovou por área — e sem
fit não há timing nem potência: o wrapper para na primeira etapa e grava
`null`, em vez de inventar número (`repo:FR-RV-41`). As revisões `_a9` usam a
mesma família, o mesmo pacote (F23) e o mesmo speed grade (C7), mudando só o
tamanho do die, para que os números de tempo continuem comparáveis. **Nenhum
número medido no `5CEFA9F23C7` vale como número do `5CEBA4F23C7`**, e o
relatório os rotula assim.

## Rodar

Da raiz do repositório, uma revisão por vez:

```bash
docker run --rm -v "$PWD/implemetation_tests/opus_5_RISCVIM:/workspace" \
    quartus-lite:25.1 analyze --project rv32im_sc --revision rv32i \
    --workdir /workspace/fpga --output /workspace/fpga/quartus_output_rv32i
```

Troque `rv32i` pelas outras cinco revisões. Cada uma grava
`quartus_output_<revisão>/{compilation,reports,netlist,bitstream}/`, com
`reports/summary.json` machine-readable.

## O que está versionado e o que não está

`quartus_output_*/` é **evidência** e está versionado: é dele que cada número
do relatório sai (constituição, princípio 10). `db/`, `incremental_db/` e
`output_files/` são artefato regenerável e estão no
[`.gitignore`](.gitignore) — o que importa deles (`*.fit.summary`,
`*.map.summary`) é copiado para `quartus_output_<revisão>/reports/`.

## Restrição de clock

[`rv32im_sc.sdc`](rv32im_sc.sdc) restringe `clk` a **20 ns (50 MHz)** — o
mesmo período declarado em [`cpu.toml`](../cpu.toml) e o alvo de NFR-02. Sem
`.sdc` o Quartus inventaria um clock de 1 ns e qualquer Fmax lido não
significaria nada (`repo:FR-RV-38`).
