# Geração de CPUs RISC-V em VHDL com LLM guiada por especificação e julgada sem IA

*Rascunho de artigo curto. Os números da sessão aprovada e dos juízes vêm de
arquivos versionados neste repositório, com a fonte indicada no texto. Os
preços do OpenRouter, o teste rápido de escolha do modelo, as duas rodadas
anteriores à aprovada, as quedas do Docker e o caso do XOR da ALU são
registros do autor, não versionados; no texto eles vêm marcados como
"registro do autor".*

## Resumo

Pedir uma CPU inteira a um LLM e iterar até parecer certa ("vibe coding")
não deixa evidência verificável. Este trabalho apresenta o `rvgen`, uma
bancada que gera CPUs RISC-V em VHDL a partir de especificações em Markdown:
a IA decompõe a CPU em blocos, escreve um contrato por bloco aprovado por um
revisor independente, escreve VHDL e testbenches em contextos separados e só
avança quando cada bloco passa nos próprios testes. O veredito não é dado por
IA: dois juízes determinísticos, o `spec-riscv-test` (programas
`riscv-tests`) e o `rvverify` (casos próprios com modelo de referência), foram
validados antes com uma CPU escrita à mão. Com o `openai/gpt-6-luna`, uma CPU
RV32I monociclo gerada passou em 40/40 programas `rv32ui` e em 24/24 casos da
etapa RV32I do `rvverify`, com 78 chamadas ao modelo, cerca de US$ 0,14 e
nenhuma iteração de correção. A maior parte das chamadas (56%) foi gasta expandindo testes de
componente, e os defeitos encontrados estavam na orquestração, não no modelo.
Com a referência da extensão M num arquivo próprio (`specs/riscv-rv32m.md`),
o mesmo modelo gerou uma CPU RV32IM que passou em 48/48 programas (40
`rv32ui` + 8 `rv32um`), com 68 chamadas, cerca de US$ 0,13 e nenhuma correção
do VHDL. Evoluindo a CPU RV32I aprovada em vez de gerar do zero (o gerador
roda os testes existentes, planeja a mudança pelo diff das specs e altera só
os blocos necessários), a CPU RV32IM passou em 48/48 com 26 chamadas e cerca
de US$ 0,06, reescrevendo 2 dos 5 blocos.

## 1 Introdução

Gerar hardware com LLM tem um problema que software não tem na mesma medida:
o erro só aparece em simulação, e um testbench escrito pela mesma IA que
escreveu o RTL tende a confirmar o que o RTL faz, não o que a especificação
pede. O caminho informal (pedir, simular, colar o erro de volta, pedir de
novo) produz no máximo um circuito que passou nos testes que alguém lembrou
de rodar.

A proposta aqui é tratar a geração como engenharia dirigida por
especificação (*spec-driven*): o contrato da CPU é um conjunto fixo de
arquivos Markdown, cada etapa da IA produz um artefato verificável, e o
veredito final vem de ferramentas que não usam IA. As contribuições são:

1. Um fluxo de geração em fases (`rvgen/`), com contrato por bloco, revisor
   independente, pilha de componentes com portões e testbench escrito sem ver
   o VHDL (seção 2).
2. Dois juízes determinísticos e uma CPU gabarito escrita à mão que os valida
   antes de eles julgarem qualquer CPU gerada (seção 2.3).
3. Um experimento completo com custo, tokens e chamadas por fase registrados
   em `experimentos/luna6_prof_3/` (seção 4).
4. A lista de defeitos do gerador que só apareceram rodando de verdade, cada
   um com o commit que o corrigiu (seção 4.4).

## 2 Método

### 2.1 Especificação como prompt

O contrato está em `specs/`. Três arquivos viram o prompt de sistema do
gerador (`rvgen/contrato.py`, constantes `CPU_SPEC`, `VHDL_SPEC`,
`RV32I_SPEC`):

- `specs/cpu.md`: ISA e microarquitetura ("RV32I single cycle") e a entidade
  `cpu` exata, cujas portas formam um barramento virtual (ROM e RAM ficam fora da
  CPU, fornecidas pelo validador);
- `specs/vhdl.md`: regras do VHDL aceito;
- `specs/riscv-rv32i.md`: referência da ISA.

O prompt dos testbenches usa também `specs/testes.md`. A variável
`RVGEN_SPECS_DIR` troca a pasta de onde esses arquivos saem, o que permite
gerar com uma variante das specs sem tocar em `specs/` (seção 2.4).

### 2.2 Fases do `rvgen`

O fluxo está desenhado em `docs/projeto.html` (parte 1); a implementação
está em `rvgen/agente.py`.

1. **Inventário de instruções.** A IA descreve cada mnemônico da ISA; o
   gerador confere que a lista é exatamente a exigida (`architecture.json`).
2. **Decomposição.** A IA divide a CPU em blocos; o último é sempre `cpu`, e
   a ordem é topológica (`validar_arquitetura`).
3. **Contrato por bloco com revisor independente.** Para cada bloco, a IA
   escreve `component_specs/<bloco>.comp_spec.txt` (tempo, reset,
   comportamento, operações, casos de borda, estratégia de teste). Um revisor,
   em chamada separada e sem o histórico do redator, responde `APPROVED` ou
   `REVISE` com evidência; o redator corrige até o limite de tentativas.
4. **Pilha de componentes com portões** (`--gates-componentes`). Folhas
   primeiro: o bloco é escrito, compilado com apenas as dependências já
   aprovadas, testado e congelado por hash em `componentes_aprovados/`.
5. **Testbench escrito sem ver o VHDL.** O prompt do testbench cocotb recebe
   só o contrato e as portas. Com `--testes-componentes` o teste é ampliado
   caso a caso (orquestração incremental); com `--regressoes-componentes`
   cada falha corrigida vira teste permanente.
6. **Triagem.** Quando um teste falha, a causa é classificada como VHDL,
   testbench, contrato ou ambígua; regras objetivas (largura de porta, API do
   cocotb 2) vencem a opinião do modelo.
7. **CPU integrada.** O bloco `cpu` é o último degrau da pilha; depois o
   `spec-riscv-test` roda um programa de fumaça e a suíte completa.
8. **Laço de correção.** Para cada falha oficial, a IA reescreve um único
   arquivo; se o placar piorar, a mudança é desfeita. O orçamento é
   `--iteracoes` (padrão 12).

A IA só escreve em `<pasta>/src/*.vhd`; todo o resto (prompts, respostas,
tokens, testes, relatórios) fica em `<pasta>/.rvgen/sessao-*/`. Antes do
veredito o gerador confere por hash que nenhum arquivo do validador mudou.

### 2.3 Juízes sem IA e o gabarito

- **`spec-riscv-test`** (`spec-riscv-test/`, código do professor da
  disciplina) compila os programas `rv32ui-p-*` do `riscv-tests`, roda cada
  um em GHDL contra a interface de `specs/cpu.md` e lê o resultado pelo
  `tohost`. É a única autoridade do veredito do `rvgen`
  (`specs/constitution.md`).
- **`rvverify`** (`rvverify/`) valida entregas descritas por `cpu.toml` com
  casos próprios cujos valores esperados vêm de um modelo Python, não do RTL.

Um juiz também pode estar errado. Por isso existe `cpus/rv32i_gabarito/`, uma
CPU RV32I monociclo escrita à mão num único arquivo no contrato virtual: se um
juiz a reprova, o defeito está no juiz. Foi assim que apareceram dois defeitos
do `rvverify` (seção 4.4).

### 2.4 Iterar nas specs

Como a especificação é o insumo principal, o repositório tem um app local
(`python -m iteracoes`, `iteracoes/README.md`) que congela uma base em
`iteracoes/base/specs/` e cria cópias numeradas `iteracoes/it-NNN/specs/` com
diff, checagens do contrato e o prompt resultante. Uma iteração é testada com
`RVGEN_SPECS_DIR=iteracoes/it-NNN/specs python -m rvgen gerar ...`. O app
nunca chama a IA.

## 3 Montagem experimental

| Item | Valor |
|---|---|
| Modelo | `openai/gpt-6-luna` via OpenRouter, o mesmo em todos os papéis |
| Preço | US$ 0,10 por 1M tokens de entrada, US$ 0,50 por 1M de saída (tabela do OpenRouter em 29/10/2026; registro do autor) |
| Temperatura | 0,2 por padrão; 0,0 na revisão semântica do contrato (13 chamadas) e na orquestração da expansão de testes (23 chamadas). As 4 chamadas de `revisao_especificacao` usaram o padrão (campo `temperatura` dos eventos `llm`) |
| Ambiente do veredito | imagem `rafaelcorsi/pl-descomp-cocotb` fixa por digest (GHDL 2.0.0, cocotb 2.0.0, Python 3.11.2) + `gcc-riscv64-unknown-elf` 12.2.0 (Debian 12, versão fixa) + `riscv-tests` no commit `3df703cd52d5f0d8224e3c50bf03c6cb70efff98` (2026-10-19); empacotado em `docker/veredito/Dockerfile` |
| Alvo | RV32I monociclo (`specs/cpu.md`) |
| Fluxo | `--testes-componentes --gates-componentes --regressoes-componentes` |
| Tetos | `--max-casos-teste 4` (padrão 32); `--iteracoes` 12 e 3 revisões semânticas por componente (evento `inicio` de `sessao.jsonl`) |

O `--max-casos-teste 4` não está no evento `inicio`: a sessão começou antes
do commit `f59dcc6`, que passou a gravar esse limite. A evidência é indireta:
o `sessao.jsonl` tem 20 eventos `candidato_lote_executado`, 4 para cada um dos
5 blocos.

**Escolha do modelo** (registro do autor). O `.env` usava antes
`openai/gpt-5.6-luna` (US$ 0,20 / 1,20 por 1M tokens). Num teste rápido com o mesmo pedido de ALU,
o `gpt-6-luna` respondeu em 6 s com 548 tokens de saída (cerca de
US$ 0,0003) e o `gpt-5.6-luna` em 8 s com 671 tokens (cerca de US$ 0,0008);
as duas ALUs compilaram no GHDL. O `gpt-6-luna` foi usado no experimento.

## 4 Resultados

### 4.1 Gabarito

| CPU | Origem | `spec-riscv-test` | `rvverify` |
|---|---|---|---|
| `cpus/rv32i_gabarito` | escrita à mão, 1 arquivo, contrato virtual | 40/40 `rv32ui` | 24/24 RV32I |
| `cpus/rv32im_gabarito` | o gabarito acima mais a extensão M | 48/48 (`rv32ui` + `rv32um`); 8/8 só no M | 24/24 RV32I (etapa M pulada) |

A CPU de referência passa em todos os casos dos dois juízes, o que é condição
para que uma reprovação de CPU gerada aponte para a CPU e não para o juiz. O
`spec-riscv-test` a aprova; no `rvverify`, 24/24 é a etapa RV32I
(`--etapa rv32i`), e o veredito dele é `parcial`, porque só a suíte completa
aprova e a etapa RV32M exige um generic que o contrato atual não tem. O mesmo
vale para a CPU gerada (seção 4.2).

Para o M, o controle negativo também foi medido: o `rv32i_gabarito`, que não
tem M, passa em 0/8 programas `rv32um`, e o `rv32im_gabarito` em 8/8. Os
programas do M de fato exercitam o M. Não existe CPU "só M": o M é uma
extensão da base inteira, e os programas `rv32um` usam instruções do I.

### 4.2 Experimento `luna6_prof_3`

A IA decompôs a CPU em `immediate_generator`, `register_file`, `alu`,
`decoder` e `cpu` (o `cpu` depende dos outros quatro;
`experimentos/luna6_prof_3/architecture.json`).

| Medida | Valor |
|---|---|
| VHDL gerado | 647 linhas: `alu` 73, `cpu` 290, `decoder` 210, `immediate_generator` 23, `register_file` 51 |
| `spec-riscv-test` | 40/40 (fumaça 1/1, suíte 40/40) |
| `rvverify` | 24/24 na etapa RV32I, veredito `parcial` (`cpu.toml` escrito depois, só para essa checagem) |
| Iterações de correção no laço do juiz | 0 |
| Chamadas ao modelo | 78 |
| Tokens | 743.978 de entrada, 124.821 de saída |
| Custo | cerca de US$ 0,137 |
| Tempo de resposta do modelo (somado) | 23,6 min |

Fonte: `experimentos/luna6_prof_3/.rvgen/sessao-20261104-171911/sessao.jsonl`
(eventos `llm` e `spec-riscv-test`) e
`.../spec-riscv-test/suite/report.json`. O commit `5068458` versiona a CPU e a
sessão.

A CPU foi aprovada na primeira passagem pelo juiz: todas as falhas foram
resolvidas antes, dentro da pilha de componentes.

### 4.3 Onde as chamadas foram gastas

| Fase (`fase` no `sessao.jsonl`) | Chamadas |
|---|---|
| `orquestracao_expansao_testbench` | 23 |
| `caso_publico_isolado` | 21 |
| `revisao_semantica_especificacao` | 13 |
| `especificacao_componente` | 5 |
| `escrita` (VHDL) | 5 |
| `testbench` | 5 |
| `revisao_especificacao` | 4 |
| `instrucoes` | 1 |
| `decomposicao` | 1 |
| **Total** | **78** |

As duas primeiras linhas são expansão de testes de componente: 44 de 78
chamadas (56%). Escrever o VHDL custou 5 chamadas.

**Custo total do modelo no experimento** (registro do autor: essas rodadas e
as quedas do Docker não estão versionadas). Antes da rodada aprovada, duas
rodadas pararam em defeitos do `rvgen`, com 15 e 12 chamadas (cerca de
US$ 0,03 e US$ 0,02). Somando tudo: 105 chamadas, cerca de 968 mil tokens de
entrada, 183 mil de saída e US$ 0,19. A sessão aprovada foi retomada 3 vezes
com `rvgen retomar`: duas por defeitos corrigidos no meio e uma porque o
Docker Desktop travou (erro 500 da API, resolvido com
`docker desktop restart`). O Docker caiu 2 vezes durante as rodadas.

### 4.4 Defeitos que só apareceram rodando de verdade

Todos foram corrigidos com teste automatizado.

| # | Componente | Defeito | Efeito | Commit |
|---|---|---|---|---|
| 1 | `rvgen` (contrato) | O revisor semântico tinha ordem de não exigir decomposição e recusava o contrato do `cpu` por instanciar os blocos, o que `_requisito_integracao_top` exige | O laço não convergia em 3 tentativas e a geração abortava antes do VHDL | `e492450` |
| 2 | `rvgen` (executor) | Procurava um Python ao lado do `spec-riscv-test` (venv) | Com o testador fora de venv, o primeiro teste de componente nem rodava | `f5fb23b` |
| 3 | `rvgen` (orquestrador de testes) | Recusava `"prerequisites": []` (lista vazia é falsa em Python) | A geração parava no primeiro teste incremental | `f59dcc6` |
| 4 | `rvgen retomar` | Ignorava o `--max-casos-teste` da sessão original | Voltava a 32 casos | `f59dcc6` |
| 5 | `rvgen` (resultado) | O `resultado.json` de uma sessão retomada contava só a última execução, e o `rvgen comparar` e o app de iterações liam esses campos | `"chamadas": 2` em vez de 78 | corrigido na rodada de limpeza seguinte: o `resultado.json` ganhou o bloco `sessao` com os totais, e o `comparar` e o app de iterações passaram a mostrar a sessão inteira (num `resultado.json` antigo, somando os eventos `llm` do `sessao.jsonl`) |

Nas rodadas da ablação do M (seção 4.9), mais dois:

| # | Componente | Defeito | Efeito | Commit |
|---|---|---|---|---|
| 6 | `rvgen` (regressão) | O pedido de teste de regressão manda "um teste para a falha e pelo menos três casos de borda", mas o validador exigia exatamente um teste | Respostas com 5 e 6 testes recusadas; a geração abortou (`luna6_abl_m_reduzida_1`) | `66ba857` |
| 7 | `rvgen` (testes de componente) | Um teste gerado fazia `await clock.start()` (cocotb 2) e simulava para sempre; o executor só desiste depois de 1 h | Rodada parada por quase 10 min até o GHDL ser encerrado à mão (`luna6_abl_m_completa_1`); agora o GHDL roda com `--stop-time=1ms` | `66ba857` |

Um oitavo problema ficou em aberto: o laço de correção do juiz encerra a
investigação depois de hipóteses refutadas sem tentar uma correção, mesmo
com rodadas sobrando (seção 4.9, `luna6_abl_m_reduzida_4`).

Na mesma semana, fora do `rvgen`:

- `rvverify`: o `tb_virtual` lia `data_addr` antes de a instrução assentar, e
  o relatório de falha derrubava o `feedback`. Achado rodando o gabarito;
  corrigido em `644cba9`.
- App de iterações: uma revisão independente apontou 12 problemas, todos
  corrigidos (`3473084`, `34e34d5`).

### 4.5 Experimento `luna6_im_1` (RV32IM)

Mesmo modelo e mesma configuração da seção 4.2, mais `--max-chamadas 150`,
com as specs da iteração `iteracoes/it-001`: idênticas a `specs/` exceto pela
linha de declaração `- RV32IM single cycle`. Com ela, o `rvgen` junta
`specs/riscv-rv32m.md` ao prompt e o juiz roda 48 programas.

| Medida | Valor |
|---|---|
| `spec-riscv-test --isa rv32im` | 48/48; 8/8 rodando só os programas `rv32um` |
| Chamadas | 68, numa execução só (sem retomada) |
| Tokens | 740.595 de entrada, 115.218 de saída (cerca de US$ 0,132) |
| CPU | 5 blocos, 598 linhas; ALU e M no mesmo bloco (`execution_unit`) |
| Correções | 0 no VHDL; 2 de 49 testes de componente falharam e a triagem culpou o testbench nas duas |
| Expansão de testes | 40 das 68 chamadas (59%) |

Ao preparar a rodada apareceu mais um defeito de orquestração: o `cpu.md`
cita "RV32I" numa frase fora da declaração, e trocar a declaração para RV32IM
deixava a ISA ambígua, de modo que o `rvgen` se recusava a gerar. O leitor
passou a ler a ISA só da linha de declaração.

### 4.6 Evoluir em vez de gerar do zero (`luna6_evolui_im_2` e `_3`)

`rvgen gerar --evoluir-de experimentos/luna6_prof_3`, com as specs de
`iteracoes/it-001` e a mesma configuração. O fluxo: (0) copia a CPU aprovada e
roda, sem IA, todos os testes de componente e o juiz na ISA antiga; (1) uma
chamada lê o diff entre o contrato antigo e o novo, as instruções novas, a
arquitetura, os contratos dos blocos e essa linha de base, e devolve um plano
de mudança; (2) só os blocos do plano têm contrato e VHDL atualizados, a
partir do VHDL aprovado, com os testes antigos como regressão; (3) os demais
rodam os próprios testes de novo; (4) o juiz roda na ISA nova.

| Medida | do zero (`luna6_im_1`) | evoluindo, plano restrito (`_2`) | evoluindo, decomposição livre (`_3`) |
|---|---|---|---|
| `spec-riscv-test --isa rv32im` | 48/48 (8/8 só no M) | 48/48 (8/8 só no M) | 48/48 (8/8 só no M) |
| Chamadas | 68 | 26 | 28 |
| Tokens | 740.595 / 115.218 | 388.021 / 41.988 | 380.089 / 52.818 |
| Custo estimado | US$ 0,132 | US$ 0,060 | US$ 0,064 |
| Blocos escritos | 5 de 5 | 2 de 5 (`decoder`, `cpu`) | 1 novo (`rv32m_unit`) + `cpu` |
| Onde ficou o M | `execution_unit` | dentro do `cpu` | `rv32m_unit` |
| Testes de componente | 47 de 49 | 43 de 43 | 44 de 45 |

Na primeira versão do plano (`_2`), o pedido era "a menor mudança", com
preferência por não criar blocos e limite fixo de 8 blocos, e a IA pôs
multiplicação e divisão dentro do topo `cpu`, que devia só integrar. Na
segunda (`_3`), o plano devolve a decomposição-alvo inteira e pode manter,
mudar, criar, dividir, juntar, renomear ou remover blocos; o limite virou
`--max-blocos`; e um topo com `*`, `/`, `rem` ou `mod` é recusado. A IA então
criou um bloco próprio para o M e manteve os outros quatro intactos.

Para separar as duas mudanças, a mesma evolução rodou só com a decomposição
livre, sem a proibição de conta no topo (`luna6_evolui_im_5`,
`--permitir-conta-no-topo`): a IA também criou um bloco próprio (`muldiv`),
mudou o `decoder` e deixou o `cpu` sem multiplicação, divisão ou resto. 48/48
(8/8 só no M), 38 chamadas, cerca de US$ 0,079. Com uma rodada de cada, o
efeito veio de liberar a decomposição; a proibição não foi necessária e
ficou como opção desligada por padrão (`--proibir-conta-no-topo`).

A linha de base deu 25/25 testes de componente e 40/40 no RV32I. Os três
blocos congelados ficaram byte a byte iguais aos da origem. A primeira
tentativa (`luna6_evolui_im_1`) parou no teto de 150 chamadas por um defeito
do gerador, não do modelo: o pedido de caso de teste citava `assemble_rv32i`
e o validador de uma CPU RV32IM só aceitava `assemble_rv32im`. Com uma rodada
de cada lado, a diferença de custo é um indício, não uma medida.

### 4.7 Mesma evolução com quatro modelos

A evolução da seção 4.6 (decomposição livre, sem a regra do topo) com outros
três modelos do OpenRouter, mesmas specs e flags, teto de 150 chamadas. Custo
= tokens registrados × preço público do OpenRouter em 13/11/2026
(`rvgen comparar`).

| Modelo | `spec-riscv-test` | Chamadas | Tokens | Custo | Tempo | Correções | Bloco do M |
|---|---|---|---|---|---|---|---|
| `openai/gpt-6-luna` | 48/48 | 38 | 501.848 / 56.953 | US$ 0,079 | 14 min | 0 | `muldiv` |
| `openai/gpt-6-sol` | 48/48 | 55 | 642.594 / 50.811 | US$ 1,79 | 12 min | 0 | `m_unit` |
| `google/gemini-4-carbon` | 48/48 | 38 | 637.481 / 153.150 | US$ 2,81 | 42 min | 0 | `muldiv_unit` |
| `anthropic/claude-sonnet-5.5` | 48/48 | 116 | 2.830.786 / 267.544 | US$ 8,34 | 35 min | 2 | `multiplier` + `divider` |

Todos passaram e todos puseram o M num bloco próprio, sem tocar `alu` e
`register_file`. Para esta tarefa, o modelo mais barato teve o mesmo
resultado do juiz por uma fração do custo. A primeira rodada do Sonnet parou
por um defeito do gerador, não do modelo: o leitor de contrato contava
menções a `## Edge cases` no meio do texto como títulos repetidos.

### 4.8 Telemetria por fase

O comando `python -m rvgen telemetria` lê o `sessao.jsonl` e soma, por grupo
de fases, chamadas, tokens, tempo de resposta do modelo, tempo de simulação
(GHDL/cocotb e `spec-riscv-test`, sem IA), falhas de simulação, recusas do
validador (regras determinísticas do `rvgen`: caso ou plano de teste
recusado, plano de evolução inválido), recusas do revisor (contrato
reprovado pela IA revisora) e erros do provedor. É o mesmo tipo de
telemetria por estágio que o UCAgent usa para comparar modelos. Os grupos
são: planejamento (instruções, decomposição, plano de evolução), contratos
(escrita e revisões), VHDL, testes (testbench e expansão de casos), correção
dentro da pilha de componentes (triagem, diagnóstico, correção de
testbench) e juiz (laço de correção guiado pelo `spec-riscv-test`). Para as
quatro evoluções da seção 4.7:

| Modelo | Planej. | Contratos | VHDL | Testes | Correção | Juiz | Recusas validador | Recusas revisor | Falhas de simulação | Min. modelo | Min. simulação | Custo dos testes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| `gpt-6-luna` | 2 | 6 | 3 | 27 (71%) | 0 | 0 | 0 | 0 | 0 | 10,7 | 2,7 | 61% |
| `gpt-6-sol` | 3 | 8 | 4 | 36 (65%) | 4 | 0 | 0 | 0 | 4 | 7,9 | 3,0 | 62% |
| `gemini-4-carbon` | 2 | 6 | 3 | 27 (71%) | 0 | 0 | 0 | 0 | 0 | 38,6 | 2,9 | 69% |
| `claude-sonnet-5.5` | 2 | 21 | 5 | 86 (74%) | 2 | 0 | 20 | 5 | 2 | 28,9 | 4,3 | 67% |

Colunas de fase em chamadas ao modelo. "Min. modelo" é o tempo de resposta
somado, não o relógio de parede da tabela 4.7. "Custo dos testes" é a
fração do custo estimado gasta no grupo testes.

- **Os testes dominam em todos os modelos:** 65% a 74% das chamadas e 61% a
  69% do custo; o VHDL fica entre 4% e 8% das chamadas. O achado da seção
  4.3 (uma rodada, um modelo) se repete nos quatro.
- **Nenhum modelo usou o laço do juiz:** 0 chamadas no grupo juiz. Todas as
  falhas foram resolvidas dentro da pilha de componentes, antes do veredito.
- **Onde o Sonnet gastou mais:** 20 recusas do validador nos testes (casos e
  planos de teste recusados por regra) e 5 contratos reprovados pelo
  revisor explicam boa parte das 116 chamadas, contra 0 e 0 no luna 6.
- **O Gemini é lento, não verboso em chamadas:** o mesmo número de chamadas
  do luna 6 (38), mas 3,6 vezes o tempo de modelo, com 2,7 vezes mais
  tokens de saída.

Desde este comando, o evento `llm` também registra quantos pedidos HTTP
foram repetidos por falha transitória (`repeticoes_rede`); nas sessões
acima, gravadas antes, esse número não existe. n = 1 por modelo.

### 4.9 Ablação da injeção de conhecimento do M

O UCAgent relata que o Qwen3-Coder-Plus errou o valor esperado de −2^31 ÷ −1
e aponta a injeção de conhecimento de domínio como lacuna (seção 6). Aqui o
conhecimento do M está escrito em `specs/riscv-rv32m.md`: tabela de
codificação, regras gerais, os casos de divisão por zero e overflow, 12
exemplos e notas para VHDL. A pergunta: é isso que faz o modelo acertar o M?

Duas variantes, geração do zero com o `gpt-6-luna`, as mesmas flags da
`luna6_im_1` (seção 4.5) e `--max-chamadas 150`:

- **completa:** `iteracoes/it-001` (a spec inteira);
- **reduzida:** `iteracoes/it-002`, em que o `riscv-rv32m.md` ficou só com o
  cabeçalho e a tabela de codificação, sem regras gerais, casos especiais,
  exemplos e notas para VHDL.

Antes de rodar, uma frase fixa do `rvgen/contrato.py` que mandava tratar
"division-by-zero and signed-overflow semantics" foi retirada (commit
`2466bcb`): ela entraria no prompt mesmo com a spec reduzida. Com a dica só
na spec, o prompt da variante reduzida não cita divisão por zero nem
overflow do M. As duas variantes rodaram com o mesmo código.

| Rodada | Spec do M | Juiz (1ª suíte = final) | Só M | Chamadas | Tokens (entrada / saída) | Custo |
|---|---|---|---|---|---|---|
| `luna6_abl_m_completa_1` | completa | 48/48 | 8/8 | 70 | 721.671 / 107.470 | US$ 0,126 |
| `luna6_abl_m_completa_2` | completa | não chegou ao juiz (revisão do contrato do `cpu` não convergiu) | — | 15 | 172.427 / 43.618 | US$ 0,039 |
| `luna6_abl_m_completa_3` | completa | 48/48 | 8/8 | 67 | 715.218 / 106.130 | US$ 0,125 |
| `luna6_abl_m_completa_4` | completa | 48/48 | 8/8 | 64 | 678.124 / 106.229 | US$ 0,121 |
| `luna6_abl_m_reduzida_1` | reduzida | não chegou ao juiz (defeito 6 da seção 4.4, corrigido) | — | 44 | 403.386 / 78.784 | US$ 0,080 |
| `luna6_abl_m_reduzida_2` | reduzida | 48/48 | 8/8 | 84 | 851.149 / 134.360 | US$ 0,152 |
| `luna6_abl_m_reduzida_3` | reduzida | 48/48 | 8/8 | 84 | 933.670 / 132.569 | US$ 0,160 |
| `luna6_abl_m_reduzida_4` | reduzida | **1/48** (laço do juiz não corrigiu) | 0/8 | 132 | 1.390.387 / 376.234 | US$ 0,327 |

Todas as CPUs foram julgadas de novo por fora (`spec-riscv-test --isa
rv32im`, a suíte inteira e só os 8 programas `rv32um`), com o mesmo placar.
Custo = tokens × preço público do OpenRouter em 23/11/2026; total da
ablação, cerca de US$ 1,13. A `completa_3` e a `reduzida_3` foram cortadas
por uma queda da sessão do assistente e retomadas uma vez com o mesmo código.

O que os números dizem, com n = 3 por variante:

- **Tirar o conhecimento da spec não mudou o acerto do M.** Das 6 CPUs que
  chegaram ao juiz, as 5 aprovadas passaram em 8/8 `rv32um` na primeira
  suíte. Os contratos das oito rodadas, inclusive das quatro reduzidas,
  citam divisão por zero e overflow, e as sete que chegaram a escrever o
  VHDL tratam −2^31 ÷ −1 explicitamente. O
  `gpt-6-luna` traz essa semântica de memória; a lacuna que o UCAgent viu no
  Qwen3-Coder-Plus não apareceu neste modelo.
- **A reprovação da `reduzida_4` não é do M.** A `control_unit` e a `alu`
  combinaram códigos `alu_op` diferentes: a `control_unit` manda `01010`
  para o `LUI` (passar o imediato) e a `alu` executa `MUL` com esse código;
  o mesmo desencontro vale para as operações do M. Cada bloco passou nos
  próprios testes; o erro está no contrato entre eles, e quebra 47 dos 48
  programas, inclusive o `add`. É a primeira rodada em que o laço de
  correção do juiz trabalhou de verdade: a investigação formulou a hipótese
  certa ("o LUI não produz o imediato U"), o revisor causal chegou a citar
  "a implementação de MUL suspeita", mas depois de duas hipóteses refutadas
  o laço terminou "sem nova correção autorizada", com 9 das 12 rodadas sem
  uso. Com uma rodada, não dá para dizer se a spec reduzida contribuiu para
  o desencontro.
- **Custo:** as aprovadas com a spec completa usaram 64 a 70 chamadas
  (US$ 0,121 a 0,126); com a reduzida, 84 (US$ 0,152 a 0,160). As falhas de
  componente que levaram a correções de VHDL, nas duas variantes, foram no
  `register_file` (índice 0 fora do vetor) e no endereço de load do `cpu`,
  nenhuma no M. A diferença de custo é indício, não medida.

### 4.10 Os testes gerados pegam erros? (mutação)

O `python -m rvgen mutacao` cria mutantes de primeira ordem de um bloco de
uma CPU aprovada (troca de operador relacional, aritmético e lógico,
constante, bit de seleção, `signed`/`unsigned`) e roda em cada um três
níveis de teste: os testes de componente do próprio bloco, os do topo `cpu`
(ambos escritos pela IA) e o `spec-riscv-test`. Mutante que não compila sai
da conta; a CPU original precisa passar em tudo antes. Os sobreviventes são
classificados por um oráculo sem IA (`rvgen/oraculo_m.py`), que compara o
bloco com um modelo Python do M nos 256 pares de 16 valores de borda: o
que o oráculo mata escapou de todos os testes; o que ele não mata conta
como equivalente.

| CPU | Bloco | Mutantes (viáveis) | Equivalentes | Testes do bloco | Testes do `cpu` | Juiz | Escaparam de tudo |
|---|---|---|---|---|---|---|---|
| `luna6_evolui_im_5` | `muldiv` | 66 (50) | 7 | 8/43 (19%) | 1/43 (2%) | 33/43 (77%) | 10 |
| `luna6_evolui_im_3` | `rv32m_unit` | 82 (66) | 6 | 16/60 (27%) | 1/60 (2%) | 50/60 (83%) | 10 |

Percentuais sem os equivalentes. Fonte: `experimentos/<cpu>/mutacao/<bloco>.json`.

- **Os testes que a IA escreveu pegam pouco:** 19% e 27% dos mutantes, e
  nada que o juiz não pegue (nenhum mutante foi morto só pelos testes de
  componente). Com `--max-casos-teste 4`, o `muldiv` tem 5 testes: 4
  multiplicações e uma `DIVU`, nenhum de divisão com sinal, resto ou
  divisor zero.
- **O juiz oficial pega a maioria, não tudo:** 77% e 83%.
- **Os 20 que escaparam estão nas guardas de overflow** de `DIV` e `REM`
  (por exemplo, `and` trocado por `or` faz `x ÷ −1` dar `0x80000000` para
  todo `x`). O `riscv-tests` só divide por −1 o próprio −2^31, e os testes
  gerados não dividem por −1. São defeitos reais que a CPU aprovada poderia
  ter e que nenhum dos dois níveis veria.
- **Equivalentes:** a guarda de overflow do `REM` é redundante (`x rem −1`
  já é 0 no `numeric_std`), e `rem` e `mod` coincidem em operandos sem
  sinal.

Para o paper, isto responde "a IA testa bem?" de forma objetiva: os testes
de componente servem de portão barato durante a geração, mas não substituem
o juiz oficial, e o juiz oficial também tem pontos cegos que um oráculo
dirigido aos casos de borda da spec fecha.

## 5 Discussão

**O custo está na expansão de testes.** Mais da metade das chamadas (44 de
78) foi gasta ampliando os testbenches de componente, contra 5 para escrever
o VHDL. Isso já com `--max-casos-teste` reduzido de 32 para 4. O resultado
sugere que o próximo ganho de custo está em gerar casos em lote ou de forma
determinística a partir do contrato, não em trocar o modelo do RTL. A
telemetria dos quatro modelos (seção 4.8) mostra o mesmo padrão em todos:
65% a 74% das chamadas vão para os testes.

**Os defeitos foram de orquestração, não do modelo.** Nenhum dos cinco
defeitos da seção 4.4 era erro de VHDL da IA; todos eram do gerador (prompt
contraditório, ambiente, validação de JSON, estado de retomada,
contabilidade). Eles só apareceram com um modelo real e um ambiente real,
apesar da suíte de testes do repositório. Bancadas de geração precisam ser
testadas de ponta a ponta com um modelo barato antes de servir de
instrumento de medida.

**O revisor pegou um erro real.** Nas rodadas não versionadas com o
`gpt-6-luna` (registro do autor), o revisor
semântico recusou um contrato da ALU cujo valor esperado de XOR estava errado
(`0x9922AA55` em vez de `0x9966AA55`) antes que ele virasse teste. Sem o
revisor, o testbench reprovaria uma ALU correta e a triagem teria de
descobrir que o erro estava no teste. Os eventos `especificacao_reprovada` da
sessão aprovada mostram outros exemplos do mesmo tipo (estratégia de teste
contraditória, rótulo trocado entre comparação com e sem sinal).

**Spec mais curta não piorou o M; contrato entre blocos sim.** Na ablação
(seção 4.9), retirar os casos especiais do `riscv-rv32m.md` não fez o
`gpt-6-luna` errar o M em nenhuma das CPUs que chegaram ao juiz. A única
reprovação veio de dois blocos que combinaram códigos `alu_op` diferentes, e
o laço de correção do juiz, exercitado pela primeira vez, não a resolveu.
Isso sugere investir em checagem automática das interfaces entre blocos
(por exemplo, o código de operação ser fixado num contrato compartilhado),
não em mais texto sobre a ISA.

**Testes gerados são portão, não prova.** Os testes de componente que a IA
escreveu mataram de 19% a 27% dos mutantes do bloco do M, contra 77% a 83%
do juiz oficial (seção 4.10). Os mutantes que escaparam dos dois estão em
casos de borda que nenhum dos dois exercita.

**Juízes também precisam de gabarito.** Os dois defeitos do `rvverify`
apareceram só quando uma CPU sabidamente correta foi julgada. Sem o
gabarito, uma CPU gerada reprovada por eles seria um falso negativo
atribuído à IA.

## 6 Trabalhos relacionados

**UCAgent** (Wang et al., arXiv 2603.25768, março de 2026) é o trabalho mais
próximo. É um agente de *verificação funcional* de blocos: recebe a
especificação e o RTL já escritos e gera o ambiente de verificação, o
modelo de cobertura e os testes; não gera o RTL. Os pontos que importam
aqui:

- **Ambiente de verificação em Python** (Picker converte o DUT num pacote
  Python e o Toffee dá as abstrações), para que o modelo não escreva
  SystemVerilog, linguagem com pouco dado de treino.
- **Workflow de 31 estágios configurável**, cada estágio com um *checker*
  automático que reprova a saída e devolve o erro ao modelo. A divisão em
  estágios foi refinada olhando onde os checkers mais forçavam repetições,
  e a telemetria de tempo e falhas por estágio é usada para comparar
  modelos (a seção de limitações do mesmo texto fala em 26 estágios).
- **VCLM**, rótulos hierárquicos FG (grupo funcional), FC (função) e CK
  (ponto de checagem) que o modelo atribui na análise da especificação e
  tem de reusar no modelo de cobertura e nos testes; os checkers comparam
  nos dois sentidos (rótulo inventado é alucinação, rótulo da especificação
  sem teste é omissão).
- **Avaliação** em seis módulos (UART-16550, ALU754, um divisor inteiro
  RV32M, ICache-WayLookup, LaneFAdd, PageTableWalker) com Claude Sonnet 4.5,
  GPT-5 e Qwen3-Coder-Plus: até 98,5% de cobertura de código e até 100% de
  cobertura funcional; a geração de testes é o estágio com mais falhas; três
  defeitos de valores especiais achados no LaneFAdd, que não tinha sido
  verificado antes.
- **Limite declarado:** no divisor RV32M, o Qwen3-Coder-Plus errou
  repetidamente o valor esperado de −2^31 ÷ −1 (overflow definido pela
  ISA), e os autores apontam a injeção de conhecimento de domínio como
  trabalho futuro. Também listam como futuro a decomposição de tarefas
  feita pelo próprio modelo, já que o workflow deles é fixo e definido por
  especialistas.

O UCAgent cita três trabalhos anteriores, descritos aqui como ele os
descreve: **UVM²** (testbenches UVM gerados de especificações com modelos e
LLM, com realimentação de cobertura), **MAVF** (vários agentes em estágios:
análise da especificação, plano de verificação, especificação do testbench
e código, com revisão manual entre etapas) e **PRO-V** (verificação em
Python de ponta a ponta com um LLM como juiz).

**Posição deste trabalho.** O `rvgen` gera o RTL *e* os testes, e o
veredito final não é dado por IA nem por métrica de cobertura dos testes
gerados: é o `spec-riscv-test` rodando os programas oficiais `riscv-tests`,
validado antes com CPUs gabarito escritas à mão (seção 2.3). Isso o separa
do PRO-V, em que o juiz é um LLM, e do UCAgent, cujo resultado é a
cobertura medida sobre testes que o próprio agente escreveu. Há pontos em
comum: testes em Python (cocotb), regras determinísticas que recusam a
saída do modelo e devolvem o motivo (validador de planos e casos de teste,
triagem com regras objetivas), e telemetria por fase para comparar modelos
(seção 4.8, em que os testes também são a fase mais cara). As diferenças
que este trabalho acrescenta:

1. **O modelo decompõe o hardware.** O UCAgent verifica um bloco já
   dado, num workflow fixo, e cita a decomposição dinâmica de tarefas pelo
   modelo como futuro. No `rvgen` as fases também são fixas, mas a divisão
   da CPU em blocos é do modelo, com o topo `cpu` sempre por último e a
   ordem topológica validada por regra.
2. **Evolução incremental**: uma CPU aprovada vira outra ISA (RV32I →
   RV32IM) rodando primeiro todos os testes antigos e o juiz antigo,
   planejando a decomposição-alvo pelo diff das especificações e mudando só
   os blocos necessários; os blocos mantidos ficam congelados por hash
   (seções 4.6 e 4.7).
3. **A especificação é o insumo que se varia e se mede.** O caso que o
   UCAgent aponta como limite (overflow e divisão por zero no M) é tratado
   aqui com conhecimento escrito na especificação, e a seção 4.9 mede o que
   acontece quando ele é retirado: com o `gpt-6-luna`, nada mudou no M.
4. **A qualidade dos testes gerados é medida por mutação** contra um juiz
   independente (seção 4.10), e não pela cobertura que os próprios testes
   gerados atingem.

## 7 Ameaças à validade

- **n pequeno.** Uma rodada por configuração nas seções 4.2 a 4.8; três
  por variante na ablação (seção 4.9), o que só mostra diferenças grandes.
  Não há taxa de sucesso com intervalo de confiança.
- **Ablação com um modelo só.** O resultado da seção 4.9 vale para o
  `gpt-6-luna`; um modelo com menos conhecimento do M (como o
  Qwen3-Coder-Plus do UCAgent) pode depender da spec.
- **Oráculo da mutação é amostral.** Um mutante "equivalente" é um que não
  diverge do modelo nos 256 pares de borda testados, não uma prova formal de
  equivalência.
- **Mesmo modelo em todos os papéis.** Redator, revisor, autor do VHDL e
  autor do testbench são o mesmo modelo; a separação é só de contexto. O
  viés compartilhado é mitigado apenas pelos juízes sem IA.
- **Temperatura fixa.** 0,2 por padrão; 0,0 na revisão semântica do contrato
  (13 chamadas) e na orquestração da expansão de testes (23 chamadas). Outra
  temperatura pode mudar o resultado.
- **`riscv-tests` não é certificação.** São testes unitários; a suíte que se
  apresenta como certificação é a `riscv-arch-test`, não usada aqui.
- **Ambiente próprio do juiz.** O `spec-riscv-test` roda os programas
  oficiais num ambiente sem CSR/ECALL e relinkado em 0.
- **Escopo.** Só RV32I monociclo.
- **`--max-casos-teste` reduzido a 4.** Menos testes de componente do que o
  padrão.
- **Sessão retomada.** A rodada aprovada foi interrompida e retomada 3 vezes,
  duas delas depois de mudanças no gerador; não é uma execução contínua de
  uma única versão do código.

## 8 Trabalhos futuros

- RV32IM (o código já aceita `rv32im`; o juiz passa a incluir os programas `rv32um`).
- Rodar a `riscv-arch-test` como terceiro juiz.
- n > 1 rodadas por configuração e outros modelos, comparados com
  `python -m rvgen comparar`.
- Modelos diferentes por papel (redator, revisor, VHDL, testbench).
- Dividir `rvgen/agente.py` em módulos por fase.
- Laço de correção do juiz: tentar uma correção quando as hipóteses são
  refutadas e ainda há rodadas (seção 4.9).
- Checagem automática dos códigos compartilhados entre blocos (por exemplo,
  `alu_op`), que hoje só o juiz final pega.
- Repetir a ablação do M com um modelo local mais fraco.
- Usar o oráculo do M (e oráculos para outros blocos) como teste de
  componente durante a geração, fechando os pontos cegos da seção 4.10.

## Reprodutibilidade

Ambiente do veredito (Linux ou WSL2, na raiz do repositório; o repositório é
montado em `/repo` e o `.env` com `OPENROUTER_API_KEY` é lido de lá):

```bash
docker build -t rvgen-veredito docker/veredito

# gerar uma CPU com a mesma configuração do luna6_prof_3
docker run --rm -it -v "$PWD:/repo" rvgen-veredito \
  python3 -m rvgen gerar luna6_novo --provedor openrouter --modelo openai/gpt-6-luna \
  --testes-componentes --gates-componentes --regressoes-componentes --max-casos-teste 4 \
  --executor local

# retomar uma sessão interrompida (id impresso pelo gerar, com ou sem o prefixo sessao-);
# herda o --max-casos-teste só em sessões criadas depois de f59dcc6
docker run --rm -it -v "$PWD:/repo" rvgen-veredito \
  python3 -m rvgen retomar luna6_novo <id-da-sessao> --executor local

# juízes sobre a CPU gerada
docker run --rm -v "$PWD:/repo" rvgen-veredito \
  spec-riscv-test --cpu experimentos/luna6_prof_3 --riscv-tests /opt/riscv-tests --out out/luna6_prof_3
docker run --rm -v "$PWD:/repo" rvgen-veredito \
  python3 -m rvverify experimentos/luna6_prof_3 --etapa rv32i
```

No Git Bash do Windows, exporte `MSYS_NO_PATHCONV=1` e passe o caminho do
repositório no formato do Windows em `-v`; as variantes para Git Bash e
PowerShell estão em `docker/veredito/README.md`.

Testes do repositório:

```bash
python -m pytest                       # na raiz; sem GHDL, os testes de simulação são pulados
docker run --rm -v "$PWD:/repo" -w /repo rafaelcorsi/pl-descomp-cocotb:latest python3 -m pytest
```

Ler a sessão aprovada: ver `experimentos/README.md`.
