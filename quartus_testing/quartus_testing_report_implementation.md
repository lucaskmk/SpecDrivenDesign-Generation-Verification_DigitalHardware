# Relatório de implementação — teste de CPU no Quartus (`quartus_testing/`)

Implementado em 2026-10-07. Tudo o que está aqui foi executado de verdade, na
imagem `quartus-lite:25.1` (Quartus Prime Lite 25.1std.0 Build 1129), e cada
número abaixo sai de um relatório do próprio Quartus.

## O pedido e onde ele está

> Um arquivo Python que recebe pelo terminal a pasta de uma CPU, usa a imagem
> Docker para rodar todos os testes de Quartus que já existiam e mais estes:
> compila ou não; se não compila, o erro; se compila, frequência, memória e
> LUTs (e o resto do uso da FPGA) e potência.

| pedido | onde | o que sai |
|---|---|---|
| receber a pasta da CPU | `python quartus_testing/quartus_cpu_check.py <pasta>` | lê o `cpu.toml` da pasta: fontes na ordem de análise, topo, generics, clock |
| usar a imagem Docker | todas as chamadas ao Quartus rodam em `docker run` na imagem do Quartus | `quartus-lite:25.1` ou, se não existir, `gabrielgalazzi/imagens_projeto_descomp:25.1` |
| os testes de Quartus que já existiam | ver [as checagens](#as-checagens) | 11 checagens herdadas, cada uma com a mesma chamada do teste original, mais uma nova (`logica`) |
| **compila ou não** | seção *1. Compila?* do relatório | veredito, etapa em que parou (síntese, fitter, assembler, timing) e o motivo classificado: `erro_de_sintese`, `nao_cabe`, `nao_roteia`, `compilacao_incompleta` |
| **se não compila, o erro** | idem | cada `Error (id)` com etapa, **arquivo e linha da fonte original** (não da cópia dentro do container) e uma dica do que fazer |
| **frequência** | seção *2. Frequência* | Fmax e Fmax restrito, alvo do `.sdc`, atende ou não, slack de setup/hold, TNS, fechamento de timing e caminho crítico (de, para, chegada, células) |
| **memória, LUTs e o resto da FPGA** | seção *3. Recursos da FPGA* | ALMs, LABs, LUTs (ALUTs de lógica, de route-through e por número de entradas), registradores, bits em bloco, blocos M10K, bits em MLAB, DSP, PLLs, clocks globais, pinos, interconexão, fan-out |
| **potência** | seção *4. Potência* | total, dinâmica do núcleo, estática do núcleo e E/S, sempre como **estimativa**, com a confiança declarada pelo Quartus |

## Como usar

Pré-requisitos: Python 3.11+ (usa `tomllib`, como o `rvverify`), Docker rodando
e a imagem do Quartus disponível. A imagem publicada basta, sem `docker tag`:

```bash
docker pull gabrielgalazzi/imagens_projeto_descomp:25.1
```

Da raiz do repositório:

```bash
python quartus_testing/quartus_cpu_check.py cpus/rv32i_pipeline
python quartus_testing/quartus_cpu_check.py cpus/rv32i_pipeline --isa ambas      # RV32I e depois RV32IM
python quartus_testing/quartus_cpu_check.py entregas/fulano --periodo-ns 20     # alvo de 50 MHz
python quartus_testing/quartus_cpu_check.py <pasta> --device 5CEFA9F23C7 --roteamento-agressivo
```

| opção | default | para quê |
|---|---|---|
| `--saida DIR` | `quartus_testing/resultados/<nome>/` | onde ficam projeto, logs e relatórios (a default está no `.gitignore`) |
| `--device` / `--familia` | `5CEBA4F23C7` / deduzida | alvo do Fitter (FR-RV-37); a família sai do prefixo (`5C` = Cyclone V) |
| `--periodo-ns` | `[clock].period_ns` | clock alvo do `.sdc` gerado |
| `--isa padrao\|rv32i\|rv32im\|ambas` | `padrao` | `padrao` usa os generics do `cpu.toml`; as outras alternam o `rv32m_generic`, e `ambas` compila a baseline RV32I antes da RV32IM (princípio 9) |
| `--roteamento-agressivo` | desligado | liga `FITTER_AGGRESSIVE_ROUTABILITY_OPTIMIZATION`, que é o que o próprio Quartus recomenda quando o roteamento falha |
| `--preservar-logica auto\|sim\|nao` | `auto` | ver [a decisão sobre preservação](#cpu-sem-porta-de-saída-vira-design-vazio) |
| `--timeout-min` | 180 | limite de cada chamada ao Quartus; ao estourar, o container é encerrado |
| `--manter-projeto` | desligado | não apaga `db/` e `incremental_db/` (centenas de MB) no fim |
| `--imagem`, `--docker` | — | outra imagem ou outro executável do Docker |

**Saída**: `relatorio.md` (para leitura), `relatorio.json` (para outro
programa), a evidência de cada revisão em `quartus_output_<revisão>/`, no
mesmo formato do wrapper `analyze` (`compilation/`, `reports/`, `netlist/`,
`bitstream/`), e o projeto Quartus gerado (`.qpf`, `comum.tcl`, um `.qsf` por
revisão, `.sdc`, `src/`). O terminal mostra um resumo das quatro respostas.

**Exit code**: `0` quando todas as revisões compilam, `1` quando alguma não
compila e `2` para problema de entrada ou de ambiente (falta `cpu.toml`, Docker
parado, imagem ou device ausente).

## Como funciona

1. **Lê o `cpu.toml`**, mas só o que importa para síntese: `[design]` (nome,
   topo, `std`, fontes, generics, `rv32m_generic`) e `[clock]`. `[observe]`,
   `[halt]` etc. são do simulador e ficam de fora. Assim uma CPU que ainda não
   fechou o manifesto de simulação já pode ser sintetizada, e o formato novo
   `program.mode = "virtual"` da `corsi_v4` não atrapalha.
2. **Confere o ambiente.** O Docker precisa responder, a imagem precisa
   existir, `quartus_sh --version` precisa funcionar e o device precisa estar
   instalado (`get_part_list`).
3. **Gera o projeto Quartus** na pasta de saída. As fontes são **copiadas**
   para `src/` byte a byte, na ordem do `cpu.toml`. O projeto fica
   autocontido para montar no container: uma entrega aponta para
   `../../cpus/...`, que ficaria fora de uma montagem só da pasta dela.
   `comum.tcl` concentra tudo o que é comum (device, topo, VHDL-2008, fontes,
   `.sdc`). Cada `.qsf` de revisão só declara os seus generics, no mesmo
   desenho de `implemetation_tests/opus_5_RISCVIM/fpga/`. O `.sdc` faz
   `create_clock` no sinal e no período do `[clock]`.
4. **Roda o `analyze` da própria imagem** (TRV-8.7, FR-RV-41): compilação
   completa, fit, Fmax, potência e `.sof`.
5. **Roda as checagens que o `analyze` não faz.** O caminho crítico vem de
   `report_timing` em `quartus_sta` e a netlist RTL de `::quartus::rtl` em
   `quartus_map`.
6. **Lê os relatórios** (`compile.log`, `*.map.summary`, `*.fit.summary`,
   tabela *Fitter Resource Usage Summary* do `*.fit.rpt`, `*.sta.summary`,
   `fmax.log`, `*.pow.summary`, `critical_path.log`) e monta o relatório.
   Os parsers de `fit/sta/pow.summary` e do Fmax são **os do `analyze.py`**,
   importados de `docker/quartus-lite/quartus_analyzer/analyze.py` e não
   reescritos: já foram conferidos contra saída real (TRV-8.7). Os novos
   (log de compilação, tabela de recursos, caminho crítico, restrição de
   clock) foram escritos contra saída real também, e os testes usam essa
   mesma saída.
7. **Devolve a pasta ao usuário.** O Quartus roda como root no container, e
   num Docker Engine nativo os arquivos ficariam de root no host. Depois a
   ferramenta apaga `db/` e `incremental_db/`.

## As checagens

As duas primeiras rodam uma vez por execução; as outras, uma vez por revisão.
Cada uma reporta `ok`, `falhou`, `aviso` ou `pulado`. `pulado` significa que
a etapa anterior não deixou nada para checar, por exemplo timing sem fit.

| id | checagem | de onde veio | req |
|---|---|---|---|
| `imagem` | a imagem responde a `quartus_sh --version` | smoke test da imagem | TRV-8.2, ADR-015 |
| `device` | o device alvo está instalado | `quartus_smoketest/list_parts.tcl` | ADR-016, FR-RV-42 |
| `compilacao` | `--flow compile` completo | `quartus_smoketest` (TRV-8.3) e `analyze` | TRV-8.3, FR-RV-41 |
| `fit` | coube e quanto usou | `analyze` (`fit.summary`) + tabela do `fit.rpt` | FR-RV-37 |
| `logica` | a síntese não reduziu a CPU a um design vazio | **nova**, ver abaixo | NFR-RV-02 |
| `restricao` | o `.sdc` foi aplicado de verdade | `counter4.sdc` (TRV-8.4) | FR-RV-38 |
| `slack` | slack de setup/hold no pior corner | `analyze` (`sta.summary`) | FR-RV-38 |
| `fmax` | Fmax via `report_clock_fmax_summary` | `quartus_smoketest/report_fmax.tcl` | FR-RV-38 |
| `caminho_critico` | pior caminho de setup | `opus_5_RISCVIM/fpga/report_critical_path.tcl` | FR-RV-38 |
| `potencia` | potência estimada | `quartus_pow` (TRV-8.5) via `analyze` | FR-RV-39 |
| `netlist` | netlist RTL acessível sem GUI | `quartus_smoketest/report_netlist.tcl` | FR-RV-40, TRV-8.6 |
| `bitstream` | `.sof` preservado | `analyze` | FR-RV-41 |

A checagem `restricao` pega um caso que antes passava em silêncio. Se o
`[clock].signal` do `cpu.toml` não for o nome de uma porta, o Quartus ignora o
`create_clock` (Warnings 332174 e 332049), inventa um clock de 1 ns e reporta
um Fmax qualquer. A ferramenta marca esse Fmax como **não confiável**, como a
FR-RV-38 exige. O mesmo vale para clock sem restrição (Warning 332060).

## Decisões e achados

### CPU sem porta de saída vira design vazio

Foi o achado mais importante desta implementação. A primeira compilação de
`cpus/rv32i_pipeline` "passou" com **1 ALM, 0 registradores e 2 pinos**. O topo
`CPU` só tem `clk` e `rst`, porque o cocotb lê tudo por dentro da hierarquia.
Para a síntese, nada ali é observável, e o Quartus remove a CPU inteira
(`Warning (21074): Design contains 2 input pin(s) that do not drive logic`).
O mesmo vale para `cpus/rv32i_monociclo`, para `experimentos/ia_mono` e, em
geral, para toda entrega que siga `entregas/_modelo`. A `opus_5_RISCVIM` nunca
teve o problema porque expõe portas `dbg_*`, e a `corsi_v4` também não, porque
expõe as portas de memória.

A saída foi preservar os registradores sem fan-out, o equivalente ao atributo
`noprune`, sem tocar no RTL. A forma de fazer isso foi descoberta por
experimento, na mesma imagem, sobre o pipeline:

| tentativa | resultado |
|---|---|
| `set_global_assignment -name PRESERVE_FANOUT_FREE_NODE ON` | `Error (125091)`: é assignment de instância, não global |
| `set_instance_assignment ... -to *` | `Critical Warning (136017)`: wildcard ignorado → 1 ALM, 0 registradores |
| `set_instance_assignment ... -to CPU` (a entidade do topo) | sem efeito → 1 ALM, 0 registradores |
| `set_instance_assignment ... -to "\|"` (**a raiz**) | **3.778 ALMs, 5.828 registradores** |

`--preservar-logica auto`, o default, lê a entidade do topo nas fontes e liga a
preservação **só quando ela não tem nenhuma porta `out`/`inout`/`buffer`**. A
detecção acertou nas seis CPUs conferidas (`rv32i_pipeline`, `rv32i_monociclo`,
`ia_mono`, `opus_5_RISCVIM`, `corsi_v3` e `corsi_v4`). O relatório diz
quando ela foi usada e por quê. Como nada sem fan-out é podado, a área
reportada fica um pouco acima da que um topo com saídas reais daria (sinais
nunca lidos, como `m_dispatch_e`, continuam lá). Mesmo assim é um limite
superior honesto, e não o "1 ALM" de antes.

Além disso, a checagem `logica` reprova **qualquer** revisão que termine a
síntese com 0 registradores, inclusive com `--preservar-logica nao` ou quando
a entidade do topo não é achada. Nesses casos o relatório põe um aviso no
topo da revisão dizendo que os números descrevem um design vazio, e não a
CPU (NFR-RV-02).

### Outras decisões

- **A pasta de saída só é apagada se foi esta ferramenta que a criou.** Ela
  tem um marcador `.quartus_testing`, e uma `--saida` que aponte para uma pasta
  com outra coisa é recusada. Rodar de novo limpa a execução anterior, para que
  um relatório velho nunca seja lido como novo.
- **Docker Desktop só compartilha o `$HOME` por padrão.** Uma `--saida` em
  `/tmp` faz o container nem subir (`mounts denied`). A ferramenta reconhece a
  mensagem e diz o que fazer, em vez de reportar "a imagem não respondeu".
- **Generic string vazia não vai para o `.qsf`.** O Quartus recusa
  `set_parameter` com `""` (Error 125042, visto em `opus_5_RISCVIM`), e o
  default do VHDL é o mesmo caminho. O relatório lista o que ficou no default.
- **Merge sem atrito.** Fora de `quartus_testing/`, só o `REPO_MAP.md` mudou
  (uma linha na tabela de topo e a frase que conta as pastas). O
  `pyproject.toml` **não** foi tocado, então `python -m pytest` sem argumentos
  não pega estes testes. Para incluí-los, basta acrescentar
  `"quartus_testing/tests"` a `testpaths` quando for conveniente.

## Validação

### Testes automatizados (sem Docker)

`python -m pytest quartus_testing/tests` → **36 passed** (mais 5 subtests).
Cobrem a leitura do manifesto e seus erros, a detecção de porta de saída, o
projeto gerado (ordem e conteúdo das fontes, `.sdc`, `.qsf` por revisão,
opções de ferramenta, colisão de nomes) e todos os parsers contra **saída real
do Quartus**:

- os logs versionados de `implemetation_tests/opus_5_RISCVIM/fpga/quartus_output_*/`
  (não cabe, não roteia, compila, caminho crítico, `sta/pow/fit/map.summary`);
- `tests/fixtures/`, capturados nas execuções desta implementação: o erro de
  VHDL, o `map.summary` de síntese reprovada e o clock que não casa com porta.
  Há também as tabelas de recursos recortadas de dois `.fit.rpt` reais, que não
  são versionados.

A execução inteira roda com um Docker falso que devolve esses mesmos arquivos,
nos cenários "compila" e "não compila". O teste confere as checagens, o
relatório, a limpeza de `db/` e a recusa de apagar uma pasta alheia.

A suíte do host continua igual: `python -m pytest rvverify/tests rvgen/tests
quartus_testing/tests` → 208 passed, 2 failed. As duas falhas
(`rvgen/tests/test_ollama.py::TestComandoPreparar`) já existiam antes desta
implementação, com o código intocado, e não envolvem nada daqui.

### Execuções reais (Docker + Quartus 25.1)

| CPU | o que provou | resultado |
|---|---|---|
| cópia de `cpus/rv32i_monociclo` com `sinal_que_nao_existe <= 1;` na linha 47 de `mono_alu.vhd` | caminho "não compila" | exit 1, `erro_de_sintese`, `Error (10482)` apontando `mono_alu.vhd:47` **no caminho original**; 11 s |
| `counter4` (projeto de fumaça) com `[clock].signal = "clk_errado"` | Fmax sem restrição | compila, Fmax 650,20 MHz marcado **não confiável** (Warnings 332174/332049); 29 s |
| `cpus/rv32i_pipeline` sem preservação (primeira versão) | o achado acima | 1 ALM, 0 registradores, 2 pinos |
| `cpus/rv32i_pipeline --isa ambas` | fluxo completo, A/B, preservação automática | exit 0, 10/10 checagens ok nas duas revisões; 464 s no total |
| `../entregas/corsi_v4` (fora do repositório) | topo com saídas, fontes de fora do repo | exit 0, 10/10 checagens ok, sem preservação; 137 s |

### Números obtidos

Device `5CEBA4F23C7`, `.sdc` com o período do `cpu.toml` (10 ns = 100 MHz nas
três). Potência é estimativa com toggle rate default, e a confiança é a do
próprio Quartus: *Low: user provided insufficient toggle rate data*.

| | `rv32i_pipeline` RV32I | `rv32i_pipeline` RV32IM | `corsi_v4` |
|---|---|---|---|
| compila | sim (160 s) | sim (294 s) | sim (131 s) |
| Fmax (restrito) | 61,30 MHz | 5,03 MHz | 70,72 MHz |
| atende 100 MHz? | não | não | não |
| pior slack de setup / hold | −6,314 / 0,170 ns | −188,965 / 0,170 ns | −4,140 / 0,322 ns |
| caminho crítico | `execute_pipeline_register\|rd_sel_out[0]` → `fetch_pipeline_register\|instr_out[20]` | `decode_pipeline_register\|rs2_sel_out[0]` → `decode_pipeline_register\|rs1_out[8]` (317 células, 202,5 ns) | `register_file\|registers[28][22]` → `register_file\|registers[30][2]` |
| ALMs | 3.778 / 18.480 (20 %) | 6.009 / 18.480 (33 %) | 1.454 / 18.480 (8 %) |
| LABs | 593 / 1.848 (32 %) | 903 / 1.848 (49 %) | 224 / 1.848 (12 %) |
| LUTs (ALUTs de lógica) | 3.752 | 7.428 | 1.849 |
| registradores | 5.828 | 5.832 | 1.023 |
| memória em bloco (M10K / MLAB) | 0 / 0 | 0 / 0 | 0 / 0 |
| DSP | 0 / 66 | 9 / 66 (14 %) | 0 / 66 |
| pinos | 2 / 224 | 2 / 224 | 165 / 224 (74 %) |
| potência total (dinâmica / estática / E/S) | 273,94 mW (76,33 / 194,13 / 3,49) | 578,81 mW (380,16 / 195,17 / 3,49) | 301,44 mW (83,80 / 194,22 / 23,42) |

Leitura rápida: no pipeline, a extensão M custa +59 % de ALMs, 9 DSPs e
derruba o Fmax de 61 para 5 MHz. O caminho crítico passa a ter 317 células
num ciclo só, o retrato de uma divisão combinacional. Nenhuma das três usa
M10K: banco de registradores e RAM viraram flip-flops, o mesmo achado da fase
5b da `opus_5_RISCVIM`. A execução do pipeline é exatamente o que a
**TRV-8.8** pede (o fluxo contra `cpus/rv32i_pipeline` com fit, timing e
potência reais). `specs/tasks.md` não foi editado, para manter o merge
isolado. Fica a cargo de quem integrar fechar a tarefa apontando para esta
seção e rodando de novo o comando, já que `resultados/` não é versionado.

## Limitações conhecidas

- **Rótulos de Cyclone V.** A tabela de recursos usa os nomes do Fitter do
  Cyclone V (ALM, M10K, MLAB). Em outra família (`--device 10M50...`), os
  campos sem equivalente saem vazios. A tabela completa continua no
  `relatorio.json` (`tabela_do_fitter`).
- **Fmax de um corner.** `report_clock_fmax_summary` reporta o corner lento
  padrão, e o slack é o pior dos quatro corners. Por isso os dois podem
  discordar por pouco; os dois aparecem no relatório.
- **Generic do tipo string não vazia** é escrito como `"valor"` no `.qsf`, mas
  nenhuma CPU do repositório usa isso, e o caso não foi exercitado no Quartus.
- **Programa da ROM.** A síntese usa a imagem default do VHDL
  (`ROM_INIT_FILE = ""`). Uma ROM com outro programa muda a área da ROM. Não
  há opção para trocar o programa.
- **`netlist`** confirma que a netlist RTL é acessível sem GUI e conta as
  células do nível de topo (`get_rtl_cells *`, como no smoke test). Não exporta
  imagem; a FR-RV-40 continua no ramo "não é viável" da TRV-8.6.

## Arquivos

Novos, todos em `quartus_testing/`:

| arquivo | o que é |
|---|---|
| `quartus_cpu_check.py` | a ferramenta (só biblioteca padrão; importa os parsers de `analyze.py`) |
| `__init__.py` | torna a pasta um pacote, para os testes e para `python -m quartus_testing.quartus_cpu_check` |
| `tests/test_quartus_cpu_check.py` | 36 testes, sem Docker |
| `tests/fixtures/` | saída real do Quartus capturada nesta implementação (ver *Validação*) |
| `.gitignore` | ignora `resultados/` |
| `how_to_use.md` | guia curto para quem vai testar uma CPU pela primeira vez |
| `quartus_testing_report_implementation.md` | este relatório |

Alterado: `REPO_MAP.md`, com a linha de `quartus_testing/` na tabela de pastas
de topo.

Ambiente de quem implementou: o Python do sistema era 3.10 (sem `tomllib`).
O Python 3.14.7 foi instalado via `uv` (`~/.local/bin/python3.14`), e a raiz
ganhou um `.venv` (já no `.gitignore`) com `pytest`. O `python3` do sistema
não foi trocado, porque o apt do Ubuntu 22.04 depende dele.
