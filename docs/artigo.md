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
de US$ 0,06, reescrevendo 2 dos 5 blocos (n = 3 evoluções contra n = 4
gerações do zero; Mann–Whitney exato p ≈ 0,057, indício e não medida). Numa
ablação com 4 rodadas de cada lado, não detectamos diferença no acerto do M
ao retirar da spec os casos especiais e os exemplos (3 de 4 contra 2 de 4;
Fisher p = 1,0; com esse n só uma diferença muito grande apareceria): o
modelo trouxe a semântica de memória, e a única reprovação veio de dois
blocos com códigos de operação diferentes. Por mutação, nos mesmos 226
mutantes viáveis dos blocos do M de quatro modelos, os testes de componente
escritos pela IA mataram 41% (IC 95% de 35% a 48%) e o juiz oficial 80% (de
74% a 84%); a diferença vem de três dos quatro modelos, e no Gemini os
testes da IA mataram mais que o juiz. Sintetizadas no Quartus (Cyclone V,
uma síntese de cada), cinco CPUs RV32IM aprovadas e o gabarito compilam com
4,0 a 4,2 mil ALMs e Fmax de 9,8 a 10,1 MHz, longe do alvo de 100 MHz: o
caminho crítico passa pelo divisor combinacional do monociclo, e essa
métrica não separa os modelos.

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
3. CPUs RV32I e RV32IM monociclo inteiras em VHDL, julgadas por GHDL e
   `riscv-tests`, com custo, tokens e chamadas por fase registrados (seções
   4.2 a 4.8). Cada configuração rodou uma vez, exceto a geração RV32IM do
   zero (5 tentativas com a spec completa, 4 com a reduzida).
4. Evoluir uma CPU aprovada (RV32I → RV32IM) contra gerar do zero, com
   custo em dólar (seção 4.6; n = 3 contra n = 4, indício).
5. Uma ablação da spec do M (seção 4.9), que não detectou diferença, com
   n pequeno demais para afirmar que não há.
6. Mutação que compara, nos mesmos mutantes, os testes escritos pela IA com
   a suíte oficial (seção 4.10), e duas checagens sem IA (seção 4.11).
7. A lista de defeitos do gerador que só apareceram rodando de verdade, cada
   um com o commit que o corrigiu (seção 4.4), e o atrito de todas as
   sessões versionadas (seção 4.12).

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

### 2.5 Rastreabilidade por rótulos (opcional)

Inspirado no VCLM do UCAgent (seção 6), com uma diferença: os rótulos não
são criados pela IA. O catálogo `specs/rotulos.md` define 50 pontos de
checagem derivados das specs (36 do RV32I e 14 do M), numa hierarquia
`FG-*` (grupo funcional) → `FC-*` (função) → `CK-*` (ponto de checagem),
cada um com a spec de onde saiu; por exemplo `FG-RV32M` → `FC-DIV` →
`CK-DIV-ZERO` e `CK-DIV-OVERFLOW`. Com `rvgen gerar --rotulos`:

1. o contrato de cada bloco ganha a seção `## Labels`, com os `CK-*` pelos
   quais o bloco responde; rótulo fora do catálogo é recusado sem IA, e o
   `cpu`, último bloco, tem de assumir os que nenhum outro assumiu;
2. cada caso de teste cocotb começa com um comentário `# CK: ...` citando
   só rótulos do contrato do próprio bloco; caso sem rótulo ou com rótulo
   de fora é recusado;
3. o orquestrador da expansão de testes recebe a lista de rótulos do
   contrato ainda sem teste, e o `complete` é recusado uma vez enquanto
   houver rótulo sem teste e orçamento de casos;
4. no fim, `rotulos_cobertura.json` dá a cobertura de rótulos por bloco e
   da CPU (rótulos do catálogo com pelo menos um teste aprovado).

Isto não é a antiga marcação `-- REQ: FR-RV-xx`, removida porque aqueles
IDs não estavam definidos em lugar nenhum: aqui todo rótulo vem de um
arquivo versionado e é conferido nos dois sentidos (inventado e omitido).
Sem `--rotulos`, nada muda no fluxo. Ainda não vale com `--evoluir-de`.

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

Um oitavo problema apareceu na `luna6_abl_m_reduzida_4`: o laço de correção
do juiz encerrava a investigação depois de hipóteses refutadas sem tentar
uma correção, mesmo com 9 de 12 rodadas sobrando. Corrigido em `cd381bb`
(seção 4.11), mas validado só com modelo falso.

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
e o validador de uma CPU RV32IM só aceitava `assemble_rv32im`.

Juntando as três evoluções aprovadas com o luna 6 (`_2`, `_3`, `_5`: 26, 28 e
38 chamadas) e as quatro gerações do zero aprovadas com a mesma spec
completa (`luna6_im_1` e `luna6_abl_m_completa_1`, `_3`, `_4`: 68, 70, 67 e
64 chamadas, seção 4.9), todas as evoluções gastaram menos que todas as
gerações do zero. O teste de Mann–Whitney exato bilateral dá p ≈ 0,057
(U = 0; com 3 contra 4 é o menor p possível). Contagem dos eventos `llm` de
cada `sessao.jsonl`. É indício, não medida: as três evoluções não são
repetições da mesma configuração (plano restrito, decomposição livre com e
sem a regra do topo), o código do gerador mudou entre 06/11 e 23/11, e só
entram as rodadas aprovadas (a `luna6_evolui_im_1`, que parou no teto de 150
chamadas por um defeito do gerador, ficou de fora).

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

**Em todas as sessões aprovadas.** Rodando `python -m rvgen telemetria
--sem-rede` (sem buscar preços, portanto sem rede) nas 13 sessões aprovadas
do repositório (12 RV32IM e a `luna6_prof_3`), a fração das chamadas no grupo
testes vai de 49% (`luna6_abl_m_reduzida_3`, 41 de 84) a 74%
(`sonnet55_evolui_im_2`, 86 de 116), com mediana de 64%
(`luna6_evolui_im_3`, 18 de 28); n = 13, das quais 10 com o mesmo modelo
(`gpt-6-luna`). O grupo testes inclui o testbench inicial; por isso a
`luna6_prof_3` aparece com 63% (49 de 78) aqui e com 56% (44 de 78, só a
expansão) na seção 4.3.

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

O que os números dizem, com n = 3 por variante que chegou ao juiz:

- **Taxas, com intervalo.** Gerando RV32IM do zero com a spec completa
  (`luna6_im_1`, que usa a mesma `it-001`, e as quatro `completa`), 4
  aprovadas em 5 tentativas: 80%, IC de Wilson de 95% de 38% a 96%. Com a
  spec reduzida, 2 em 4: 50%, de 15% a 85%. Só dentro da ablação, 3 de 4
  contra 2 de 4: Fisher exato bilateral p = 1,0. Os intervalos se sobrepõem
  quase inteiros; com n = 4 por braço, só uma diferença de dezenas de pontos
  seria detectável. Tentativas que não chegaram ao juiz (revisão que não
  convergiu, defeito do gerador) contam como não aprovadas.
- **Não detectamos diferença no acerto do M ao tirar o conhecimento da
  spec.** Isso não é o mesmo que "não há diferença": n = 3 CPUs julgadas
  por braço não dá poder para isso. Das 6 CPUs que
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
  nenhuma no M. As três reduzidas julgadas ({84, 84, 132}) gastaram mais
  que as quatro completas aprovadas ({70, 67, 64, 68}, incluindo a
  `luna6_im_1`): Mann–Whitney exato bilateral p ≈ 0,057. Sem a `reduzida_4`,
  que reprovou e usou o laço do juiz, p ≈ 0,13. A diferença de custo é
  indício, não medida.

### 4.10 Os testes gerados pegam erros? (mutação)

O `python -m rvgen mutacao` cria mutantes de primeira ordem de um bloco de
uma CPU aprovada (troca de operador relacional, aritmético e lógico,
constante, bit de seleção, `signed`/`unsigned`) e roda em cada um três
níveis de teste: os testes de componente do próprio bloco, os do topo `cpu`
(ambos escritos pela IA) e o `spec-riscv-test`. Mutante que não compila sai
da conta; a CPU original precisa passar em tudo antes. Os sobreviventes são
classificados por um oráculo sem IA (seção 4.11), que compara as 8
operações do M com um modelo Python da ISA nos 256 pares de 16 valores de
borda: o que o oráculo mata escapou de todos os testes; o que ele não mata
conta como equivalente. Foram medidos os blocos só do M das CPUs evoluídas
pelos quatro modelos da seção 4.7, todos com `--max-casos-teste 4` (5
testes por bloco).

| Modelo | CPU / bloco | Viáveis sem equivalentes | Equivalentes | Testes do bloco (IA) | Testes do `cpu` (IA) | Juiz | Só a IA pegou | Escaparam de tudo |
|---|---|---|---|---|---|---|---|---|
| `gpt-6-luna` | `luna6_evolui_im_5` / `muldiv` | 43 | 7 | 8 (19%) | 1 (2%) | 33 (77%) | 0 | 10 |
| `gpt-6-luna` | `luna6_evolui_im_3` / `rv32m_unit` | 60 | 6 | 16 (27%) | 1 (2%) | 50 (83%) | 0 | 10 |
| `gpt-6-sol` | `sol6_evolui_im_1` / `m_unit` | 43 | 6 | 10 (23%) | 1 (2%) | 33 (77%) | 0 | 10 |
| `gemini-4-carbon` | `carbon4_evolui_im_1` / `muldiv_unit` | 42 | 7 | **37 (88%)** | 0 | 32 (76%) | **5** | 5 |
| `claude-sonnet-5.5` | `sonnet55_evolui_im_2` / `multiplier` | 10 | 0 | 10 (100%) | 0 | 10 (100%) | 0 | 0 |
| `claude-sonnet-5.5` | `sonnet55_evolui_im_2` / `divider` | 28 | 2 | 12 (43%) | 1 (4%) | 22 (79%) | 0 | 6 |

Fonte: `experimentos/<cpu>/mutacao/<bloco>.json`. "Só a IA pegou": mortos
pelos testes de componente e não pelo juiz.

- **A qualidade dos testes gerados depende do modelo, com o mesmo
  orçamento de 5 testes por bloco:** 19% a 27% nos blocos do `gpt-6-luna` e
  do `gpt-6-sol`, 43% e 100% nos do Sonnet, 88% no do Gemini. No `muldiv`
  do luna 6, os 5 testes são 4 multiplicações e uma `DIVU`; nenhum testa
  divisão com sinal, resto ou divisor zero.
- **O juiz oficial é estável e pega a maioria, não tudo:** 76% a 83% nos
  blocos que dividem. Os testes do topo `cpu` quase não exercitam o M (0% a
  4%).
- **Os testes gerados nem sempre são redundantes com o juiz:** no bloco do
  Gemini, 5 mutantes só foram pegos pelos testes de componente.
- **O que escapou de tudo está nas guardas de overflow** de `DIV` e `REM`
  (por exemplo, `and` trocado por `or` faz `x ÷ −1` dar `0x80000000` para
  todo `x`): 41 mutantes nos 6 blocos. O `riscv-tests` só divide por −1 o
  próprio −2^31. São defeitos reais que uma CPU aprovada poderia ter e que
  só o oráculo dirigido aos casos de borda vê.
- **Equivalentes:** a guarda de overflow do `REM` é redundante (`x rem −1`
  já é 0 no `numeric_std`), e `rem` e `mod` coincidem em operandos sem
  sinal.

Para o paper, isto responde "a IA testa bem?" de forma objetiva: depende
muito do modelo; os testes de componente servem de portão barato durante a
geração, mas, para a maioria dos modelos, não substituem o juiz oficial, e
o juiz oficial também tem pontos cegos que um oráculo dirigido aos casos de
borda da spec fecha. n = 1 bloco por modelo (2 no luna 6).

**Somando os 6 blocos, nos mesmos mutantes.** Recalculado mutante a
mutante dos seis `mutacao/<bloco>.json`, sem os equivalentes do oráculo.
"IA" é morto pelos testes do bloco ou do `cpu` (nestes blocos, todo mutante
que o `cpu` matou o bloco também matou). McNemar exato usa só os pares
discordantes (morto por um e não pelo outro).

| Modelo | Viáveis | IA | Juiz | Só a IA | Só o juiz | McNemar exato |
|---|---|---|---|---|---|---|
| `gpt-6-luna` (2 blocos) | 103 | 24 (23%; IC 16–32%) | 83 (81%; 72–87%) | 0 | 59 | p < 0,001 |
| `gpt-6-sol` | 43 | 10 (23%; 13–38%) | 33 (77%; 62–87%) | 0 | 23 | p < 0,001 |
| `gemini-4-carbon` | 42 | 37 (88%; 75–95%) | 32 (76%; 62–87%) | 5 | 0 | p = 0,06 |
| `claude-sonnet-5.5` (2 blocos) | 38 | 22 (58%; 42–72%) | 32 (84%; 70–93%) | 0 | 10 | p = 0,002 |
| **Total** | **226** | **93 (41%; 35–48%)** | **180 (80%; 74–84%)** | **5** | **92** | **p < 0,001** |

IC de Wilson de 95%. Ressalvas: os mutantes de um mesmo bloco não são
independentes (vêm do mesmo arquivo e são julgados pelos mesmos testes), e a
unidade que de fato varia é o bloco (6) ou o modelo (4); o IC e o p tratam
cada mutante como independente e por isso são otimistas. O total é puxado
pelo luna 6 (103 de 226). O que se sustenta é a direção em três dos quatro
modelos, e o oposto no Gemini, com p = 0,06 só.

### 4.11 Duas checagens sem IA

**Oráculo do M no nível da CPU** (`python -m rvgen oraculo-m`,
`rvgen/oraculo_m_cpu.py`). Um programa RV32IM carrega os 256 pares de borda
e executa as 8 operações do M em cada um (2.048 resultados, gravados com
`sw`); o testbench serve ROM e RAM pelas portas fixas da entidade `cpu` e
compara cada store com o modelo Python. Por usar só a entidade `cpu`, vale
para qualquer decomposição. Controles: o `cpus/rv32im_gabarito` passa e o
`cpus/rv32i_gabarito` (sem M) reprova. Resultado: **as 12 CPUs RV32IM
aprovadas do repositório passam**, inclusive nas divisões por −1 que o
`riscv-tests` não testa; só a `luna6_abl_m_reduzida_4` reprova. Cerca de 3 s
por CPU. Na mutação, classificou os sobreviventes do `muldiv` e do
`rv32m_unit` exatamente como o oráculo de bloco (`rvgen/oraculo_m.py`).

**Códigos combinados entre blocos** (`python -m rvgen interfaces`,
`rvgen/interfaces.py`). Para cada sinal do topo que liga a saída de um bloco
à entrada de outro, compara os literais de bits que o produtor atribui com
os que o consumidor decodifica (`case`/`when` e comparações). Código que um
bloco consumidor não decodifica é problema; quando o consumidor é o próprio
topo, só aviso, porque o topo costuma filtrar antes. Nas 25 CPUs do
repositório, acusa só a `luna6_abl_m_reduzida_4`: a `control_unit` emite
`alu_op` de `10010` a `10110` que a `alu` não decodifica. Limites: só olha
literais (aplica-se a 11 das 25 CPUs) e não pega um código igual com
significado diferente (o `01010` que era `LUI` de um lado e `MUL` do outro).

O laço de correção do juiz passou a receber esse resultado como evidência e
não encerra mais quando a investigação adaptativa se esgota com rodadas
sobrando (commit `cd381bb`). As duas mudanças foram testadas com modelo
falso; ainda não houve uma rodada real que precisasse delas.

### 4.12 Atrito: todas as sessões versionadas

Uma sessão por pasta de `experimentos/` (21). "Chegou ao juiz" é a suíte
final na ISA pedida; nas evoluções, a linha de base na ISA antiga não conta.
Fonte: `resultado.json` e o último evento de cada `sessao.jsonl`.

| Sessão | Modelo | Chegou ao juiz? | Aprovada? | Causa da parada |
|---|---|---|---|---|
| `luna6_prof_3` | luna 6 | sim | sim (40/40) | — (3 retomadas) |
| `luna6_im_1` | luna 6 | sim | sim | — |
| `luna6_abl_m_completa_1`, `_3`, `_4` | luna 6 | sim | sim | — |
| `luna6_abl_m_completa_2` | luna 6 | não | não | revisão do contrato do `cpu` não convergiu |
| `luna6_abl_m_reduzida_1` | luna 6 | não | não | defeito do gerador (6 da seção 4.4) |
| `luna6_abl_m_reduzida_2`, `_3` | luna 6 | sim | sim | — |
| `luna6_abl_m_reduzida_4` | luna 6 | sim | não (1/48) | reprovação; o laço do juiz não corrigiu |
| `luna6_evolui_im_1` | luna 6 | não | não | teto de 150 chamadas, causado por defeito do gerador (`assemble_rv32i`) |
| `luna6_evolui_im_2`, `_3`, `_5` | luna 6 | sim | sim | — |
| `luna6_evolui_im_4` | luna 6 | não | não | defeito do gerador (validador do plano) |
| `sol6_evolui_im_1` | gpt-6-sol | sim | sim | — |
| `carbon4_evolui_im_1` | gemini-4-carbon | sim | sim | — |
| `sonnet55_evolui_im_1` | claude-sonnet-5.5 | não | não | defeito do gerador (leitor de contrato) |
| `sonnet55_evolui_im_2` | claude-sonnet-5.5 | sim | sim | — |
| `qwen38_cluster_prof_1`, `_2` | Qwen3.8 local | não | não | infraestrutura (servidor vLLM) |

Das 21 sessões, 14 chegaram ao juiz e 13 foram aprovadas. Das 7 que não
chegaram, 4 pararam em defeito do gerador (uma delas pelo teto de chamadas
que o defeito esgotou), 2 em infraestrutura e 1 numa revisão de contrato que
não convergiu; houve 1 reprovação. As duas rodadas anteriores à
`luna6_prof_3` (registro do autor, seção 4.3) também pararam em defeitos do
gerador e não estão nesta tabela. As sessões não são amostra de uma mesma
configuração: o código e as flags mudaram entre elas, e a tabela serve para
mostrar onde se perde rodada, não para estimar uma taxa.

### 4.13 Síntese no Quartus

As cinco CPUs RV32IM aprovadas com `cpu.toml` e o gabarito RV32IM
(`cpus/rv32im_gabarito`) foram sintetizadas com
`python quartus_testing/quartus_cpu_check.py <pasta>` (Quartus Prime Lite
25.1std.0, imagem `gabrielgalazzi/imagens_projeto_descomp:25.1`), no Cyclone V
`5CEBA4F23C7`, com o clock `clk` restrito a 10 ns (100 MHz). Uma síntese por
CPU, com a semente padrão. Todas compilaram (síntese, fit, assembler e
timing).

| CPU | Modelo | Fmax (MHz) | ALMs (de 18.480) | ALUTs | Registradores | DSP (de 66) | Potência estimada (mW) | Compilação (min) |
|---|---|---|---|---|---|---|---|---|
| `luna6_evolui_im_5` | luna 6 | 9,87 | 4.071 (22%) | 6.655 | 1.023 | 9 | 836 | 63,5 |
| `luna6_im_1` | luna 6 | 10,09 | 4.202 (23%) | 6.855 | 1.023 | 9 | 897 | 53,7 |
| `sol6_evolui_im_1` | gpt-6-sol | 9,79 | 4.068 (22%) | 6.633 | 1.023 | 9 | 868 | 43,7 |
| `carbon4_evolui_im_1` | gemini-4-carbon | 10,02 | 4.095 (22%) | 6.616 | 1.023 | 9 | 827 | 57,9 |
| `sonnet55_evolui_im_2` | claude-sonnet-5.5 | 10,01 | 3.996 (22%) | 6.479 | 1.023 | 3 | 809 | 50,3 |
| `rv32im_gabarito` | gabarito | 9,90 | 4.027 (22%) | 6.503 | 1.023 | 3 | 783 | 45,4 |

Fonte de cada número, em
`quartus_testing/resultados/<cpu>/quartus_output_padrao/` (não versionado; o
`.gitignore` de `quartus_testing/` ignora `resultados/`): Fmax de
`compilation/fmax.log` e `reports/padrao.sta.summary`
(`report_clock_fmax_summary`, corner lento); ALMs, registradores e DSP de
`reports/padrao.fit.summary`; ALUTs de lógica do relatório do Fitter
(`reports/resources.json`); potência total de `reports/padrao.pow.summary`;
tempo de `duracao_compilacao_s` em `quartus_testing/resultados/<cpu>/relatorio.json`.
O resumo de cada CPU está em `quartus_testing/resultados/<cpu>/relatorio.md`.

Nenhuma CPU chega perto dos 100 MHz: o Fmax fica entre 9,79 e 10,09 MHz, e o
pior slack de setup entre −92,5 e −94,9 ns. Nas seis, o caminho crítico vai
de um registrador do banco a outro passando pelo divisor que o Quartus
inferiu para o resto (células `Mod0|auto_generated|divider` em
`reports/critical_path.log`), com 547 a 604 células. Isso é o esperado num
monociclo com divisão combinacional de 32 bits, e explica por que as seis
ficam a cerca de 3% umas das outras no Fmax: o divisor domina o tempo, não
o que o modelo escreveu em volta. A área varia de 3.996 a 4.202 ALMs (5%);
quanto dela é do divisor não foi medido.
Duas CPUs (Sonnet e gabarito) usam 3 blocos DSP e as outras 9; a causa não
foi investigada. Nenhuma usa memória em bloco (0 bits em M10K): o banco de
registradores virou flip-flops e multiplexadores.

Ressalvas: alvo de 100 MHz que nenhuma atende; mul/div em um ciclo; n = 1
por modelo e uma única síntese, sem variar semente; potência é estimativa do
Power Analyzer com taxa de chaveamento padrão (confiança *Low*, rótulo do
próprio Quartus), não medição; pinos sem atribuição (aviso 169085), então o
número é de uma CPU solta, não numa placa. Os tempos de compilação foram
medidos com a mutação da seção 4.10 rodando ao mesmo tempo na mesma máquina
(dois contêineres, cerca de 7 dos 12 núcleos), e por isso estão inflados;
servem como ordem de grandeza (45 a 64 minutos por CPU).

## 5 Discussão

**O custo está na expansão de testes.** Mais da metade das chamadas (44 de
78) foi gasta ampliando os testbenches de componente, contra 5 para escrever
o VHDL. Isso já com `--max-casos-teste` reduzido de 32 para 4. O resultado
sugere que o próximo ganho de custo está em gerar casos em lote ou de forma
determinística a partir do contrato, não em trocar o modelo do RTL. A
telemetria dos quatro modelos (seção 4.8) mostra o mesmo padrão em todos:
65% a 74% das chamadas vão para os testes (49% a 74% nas 13 sessões
aprovadas). Há uma corroboração informal, que é relato de engenheiro e não
artigo revisado: Adam Taylor ("Fourteen Local Models for RTL on a Strix
Halo", LinkedIn, 23/11/2026,
<https://www.linkedin.com/pulse/fourteen-local-models-rtl-strix-halo-adam-taylor-wrzee>)
conta que, segundo a AMD, a maior parte dos tokens dos fluxos com agente vai
para testes de regressão e depuração, não para escrever RTL, e que nenhuma
das três suítes públicas que ele rodou mede isso. Ele também relata
variação de cerca de 3 pontos entre repetições de uma mesma execução e
cinco defeitos do próprio harness que teriam corrompido a tabela em
silêncio, o mesmo tipo de problema da seção 4.4.

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

**Não detectamos efeito da spec mais curta no M; o contrato entre blocos
falhou.** Na ablação (seção 4.9), retirar os casos especiais do
`riscv-rv32m.md` não fez o `gpt-6-luna` errar o M em nenhuma das CPUs que
chegaram ao juiz (n = 3 por braço, sem poder para afirmar ausência de
efeito; a explicação pode ser memória do modelo, ver seção 7). A única
reprovação veio de dois blocos que combinaram códigos `alu_op` diferentes, e
o laço de correção do juiz, exercitado pela primeira vez, não a resolveu.
Isso sugere investir em checagem automática das interfaces entre blocos,
não em mais texto sobre a ISA; uma primeira checagem sem IA, que acusa esse
caso e nenhuma CPU aprovada, está na seção 4.11.

**A qualidade do testador varia mais que a do gerador.** Os quatro
modelos geraram CPUs aprovadas com o M correto (seções 4.7 e 4.11), mas os
testes de componente que escreveram para o M mataram de 19% (`gpt-6-luna`)
a 88% (`gemini-4-carbon`) dos mutantes, com o mesmo orçamento de testes; o
juiz oficial ficou entre 76% e 83% (seção 4.10). É no testador, o papel
que o UCAgent automatiza, que está a maior diferença entre modelos, e um
oráculo sem IA dirigido aos casos de borda fecha o que nem o juiz vê.

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
- **Avaliação**: a Tabela 1 lista seis módulos (UART 16550, ALU754, um
  divisor inteiro RV32M, ICache-WayLookup, LaneFAdd, PageTableWalker), o
  texto da seção 4.1 fala em cinco, e a seção 4.2 diz que a verificação de
  ponta a ponta foi concluída em quatro (o PageTableWalker precisou de
  humano no laço). Modelos: Claude Sonnet 4.5, GPT-5 e Qwen3-Coder-Plus; até
  98,5% de cobertura de código e até 100% de cobertura funcional; a geração
  de testes é o estágio com mais falhas; três defeitos de valores especiais
  achados no LaneFAdd, que não tinha sido verificado antes.
- **Limite declarado:** no divisor RV32M, o Qwen3-Coder-Plus errou
  repetidamente o valor esperado de −2^31 ÷ −1 (overflow definido pela
  ISA), e os autores apontam a injeção de conhecimento de domínio como
  trabalho futuro. Também listam como futuro a decomposição de tarefas
  feita pelo próprio modelo, já que o workflow deles é fixo e definido por
  especialistas.

**Os três trabalhos que o UCAgent cita**, descritos pela fonte (página do
arXiv e texto integral, abertos em 27/11/2026):

- **UVM²** (Ye et al., arXiv 2504.19959, ICCAD 2025) gera testbenches UVM
  em SystemVerilog para RTL já existente e os refina com realimentação de
  cobertura. A Tabela I avalia 9 projetos de 409 a 1.572 linhas (a
  introdução fala em 10, de 400 a 1.600), com cobertura média de código de
  87,44% e de função de 89,58%.
- **MAVF** (Liu et al., arXiv 2507.21694, DVCon China 2025) usa vários
  agentes para ir da especificação ao testbench (análise da especificação,
  estratégia de verificação, código) e se diz melhor que o processo manual
  e que um pedido único ao LLM em alguns módulos. Afiliação, número de
  módulos, papel da calibração manual e números de acerto: não
  verificados (o resumo não os traz e o PDF não pôde ser lido nesta
  revisão).
- **PRO-V** (Zhao et al., arXiv 2506.12200; v1 "PRO-V: An Efficient Program
  Generation Multi-Agent System for Automatic RTL Verification", junho de
  2025; v4 "PRO-V-R1: Reasoning Enhanced Programming Agent for RTL
  Verification", dezembro de 2025) é um agente que escreve testbenches em
  programa. O LLM-juiz não dá o veredito final: no resumo da v1 ele ajuda a
  decidir se uma falha vem do RTL ou do testbench, e na v4 valida e corrige
  as saídas escolhidas (seção 3.1). A nota vem de simulação, contra o RTL
  de ouro dos benchmarks e contra 10 mutantes por problema gerados por um
  LLM (DeepSeek-V3.2, seção 4.1 da v4).

### 6.1 Trabalhos de 2025–2026 mais próximos

Busca de 24/11/2026, reconferida em 27/11/2026 na página
`https://arxiv.org/abs/<id>` (título e resumo) e, para os números, no texto
integral (`https://arxiv.org/html/<id>`). O que não deu para conferir ficou
de fora ou está marcado.

**CPU gerada por agente.**

- **Design Conductor** (Verkor Team, 2603.08716): um agente constrói uma CPU
  RV32I+Zmmul com pipeline de 5 estágios em ordem, em Verilog; a spec manda
  conferir o comportamento contra o Spike. 12 h de execução; o texto fala em
  "dezenas de bilhões de tokens" no desenvolvimento do sistema, sem o total
  da rodada.
- **Itoh e Kadomoto** (Univ. de Tóquio, 2610.39570, submetido ao ISCAS
  2027): agentes com supervisão humana levam uma CPU de RV32I monociclo a
  RV32IM fora de ordem em FPGA (Artix-7). A aceitação usa um modelo Python
  da ISA, simulação e duas execuções na placa; a comparação de desempenho
  usa uma configuração congelada; não há custo em dinheiro.
- **VeriGraphi** (Islam et al., 2604.14550): gera RV32I em Verilog a partir
  das 238 páginas da especificação RISC-V; a descrição de cada submódulo
  passa por um auditor, e a geração é de baixo para cima (folhas primeiro);
  um agente verificador escreve o testbench a partir da especificação.
  Custo relatado: US$ 0,74.
- **ROME** (Nakkab et al., 2407.18276, MLCAD 2024): prompts hierárquicos
  para gerar um processador MIPS de 16 bits e um RISC-V de 32 bits.
- **AGON** (Li et al., 2412.20954): LLM para projetar processadores fora de
  ordem customizados, sobre uma representação intermediária própria.
- **Architect in the Loop** (Mohammed, 2512.00016): fluxo com engenheiros no
  laço; o agente divide o projeto e escreve SystemVerilog e testes cocotb,
  com um modelo Python da ISA; dois processadores, cerca de 1 milhão de
  tokens cada.
- **From Seed to BLOOM** (Cui et al., 2611.26517): um agente melhora o
  núcleo BOOM sem intervenção humana, avaliado num ambiente isolado que os
  agentes não acessam nem alteram.

**Evolução incremental.**

- **LACE** (Zheng et al., 2608.02915): acrescenta 5 extensões de instrução a
  4 núcleos RISC-V de código aberto; roda o riscv-formal no núcleo original
  e de novo no estendido; 9 execuções independentes; pass@1 médio de 72,8%.
- **IncreRTL** (Chen et al., 2603.25769): regenera só os trechos afetados
  quando o requisito muda, em módulos. Usa 1,46× de tokens relativos contra
  1,8× da regeneração completa, mas a regeneração completa acertou mais
  (pass@5 funcional 67,67 contra 61,34, Tabela 2).
- **Spec-Driven Hardware Evolution** (Zhao et al., 2608.12684): um estudo de
  caso (um bloco de datapath de TPU), com contrato executável em C/C++
  conferido com hw-cbmc.
- **CktEvo** (Shi et al., 2603.08718): benchmark de evolução de RTL em nível
  de repositório, buscando melhorar PPA sem mudar a função.

**Testes e juízes.**

- **From FIPS to FPGA** (Park et al., 2611.25339): num fluxo de agente para
  um acelerador pós-quântico, os portões de simulação mataram 303 de 399
  mutantes do Yosys (76%); o artigo usa IC de Wilson.
- **GateTruth** (Bhadra, 2608.12635): mutação para auditar testbenches de
  benchmark; no RTLLM v2.0, 72% de 46 projetos auditáveis ficam abaixo de
  95% de mutantes mortos.
- **AutoBench** (Qiu et al., 2407.03891) e **CorrectBench** (Qiu et al.,
  2411.08510): geram testbenches com LLM e medem sua qualidade com até 10
  mutantes do RTL de ouro por tarefa, gerados por LLM (AutoBench, seção 4;
  o CorrectBench reusa esses mutantes).
- **RTLReviewBench** (Mahmud, 2611.21678): revisores LLM raramente aceitam
  RTL com defeito, mas rejeitam RTL correto de 1,8% a 58,8% das vezes,
  conforme o modelo (Tabela 3).

**VHDL.** VHDL-Eval (Vijayaraghavan et al., 2406.04379, LAD 2024; 202
problemas; melhor pass@1 0,237, CodeLlama-70b com 5 exemplos);
VHDL-RepoBench (2610.05380, IEEE International Conference on LLM-Aided
Design 2026; nível de repositório); VHDLSuite (Shen et al., 2606.13735;
inclui 206 problemas); VHDLBench (Drazic et al., 2610.28676; conjunto de
dados e ajuste fino de modelos de 7B); AIvril2 (ul Islam et al.,
2412.04485; com Claude 3.5 Sonnet, 66% em VHDL contra 77% em Verilog,
Tabela 1); e The Representation Bottleneck (Fu et al., 2604.17097; VHDL de
71% a 78% contra Verilog de 83% a 88% nos três modelos). Todos medem
problemas de módulo ou de repositório; nenhum dos seis gera um processador
em VHDL.

**Especificação.** SpecRead (Huang et al., 2609.33699; 383 perguntas sobre
10 blocos IP do OpenTitan) e VClare (Zhao et al., 2607.24854; specs vagas,
contraditórias ou incompletas em tarefas Verilog de um ou vários módulos)
trabalham em módulos, não no nível de uma ISA.

### 6.2 Posição deste trabalho

O `rvgen` gera o RTL *e* os testes, e o veredito final não é dado por IA
nem por métrica de cobertura dos testes gerados: é o `spec-riscv-test`
rodando os programas oficiais `riscv-tests`, validado antes com CPUs
gabarito escritas à mão (seção 2.3). Há pontos em comum com o UCAgent:
testes em Python (cocotb), regras determinísticas que recusam a saída do
modelo e devolvem o motivo, e telemetria por fase para comparar modelos
(seção 4.8).

O que **não** é novidade, à luz da seção 6.1: gerar uma CPU RISC-V com
agente (Design Conductor, Itoh e Kadomoto, VeriGraphi, ROME, Architect in
the Loop); dividir o projeto em módulos com especificação por módulo,
auditor e geração de baixo para cima (VeriGraphi); escrever o testbench a
partir da spec sem ver o RTL (VeriGraphi, AutoBench); evoluir um projeto
existente em vez de gerar do zero (LACE, IncreRTL, Spec-Driven Hardware
Evolution); medir testes por mutação (AutoBench, CorrectBench, GateTruth,
From FIPS to FPGA).

O que este trabalho mede e a busca de 24/11/2026 não achou ocupado:

1. **Repetição com intervalo de confiança em escala de CPU.** Os trabalhos
   de CPU acima, no que lemos, não relatam taxa de aprovação com intervalo
   de confiança sobre rodadas repetidas. Aqui também
   ainda é pouco: 5 e 4 tentativas na geração RV32IM do zero (seção 4.9);
   a repetição de verdade está por fazer (seção 8).
2. **Spec contra memória do modelo no nível da ISA.** A seção 4.9 retira da
   spec o conhecimento do M e mede o efeito; SpecRead e VClare tratam specs
   de módulo. Com n = 3 por braço não detectamos diferença, o que não
   separa "o modelo sabe de cor" de "a spec não importa" (seção 7).
3. **Testes da IA contra a suíte oficial, nos mesmos mutantes.** Os
   trabalhos de mutação acima medem os testes gerados (ou os do benchmark)
   contra mutantes; a seção 4.10 põe, nos mesmos 226 mutantes, os testes da
   IA, o `riscv-tests` e um oráculo sem IA, e mostra que a suíte oficial
   também deixa passar mutantes.
4. **Evoluir contra gerar do zero com custo em dólar.** O IncreRTL compara
   tokens relativos em módulos; a seção 4.6 compara chamadas e US$ numa CPU
   inteira, com n = 3 contra 4 (indício).
5. **CPU inteira em VHDL com GHDL e cocotb.** Os trabalhos de VHDL da seção
   6.1 são benchmarks de módulo ou de repositório.

## 7 Ameaças à validade

- **n pequeno.** Uma rodada por configuração nas seções 4.2 a 4.8; 5 e 4
  tentativas na geração RV32IM do zero (seção 4.9), com IC de Wilson de 38%
  a 96% e de 15% a 85%, largos demais para comparar as variantes.
- **Contaminação.** RISC-V monociclo é material de curso e aparece em muito
  código público; o modelo pode saber a CPU e a semântica do M de cor. A
  ablação da seção 4.9 é compatível com isso: sem os casos especiais na
  spec, os contratos continuaram citando divisão por zero e overflow. Não
  há aqui como separar o efeito da spec do que o modelo já sabe; uma spec
  contrafactual (que contradiga a ISA num ponto) seria o teste.
- **Sem linha de base.** Não há rodada sem a pilha de testes de componente
  nem um pedido único ("escreva a CPU") com o mesmo modelo e o mesmo juiz.
  Por isso não dá para dizer quanto o fluxo contribui para a aprovação,
  só quanto ele custa.
- **O juiz deixa passar mutantes.** Na seção 4.10, o `spec-riscv-test`
  matou 80% dos mutantes viáveis do M (IC de 74% a 84%); 41 escaparam de
  todos os testes e só o oráculo dirigido os pegou. "Aprovada no juiz" não
  quer dizer "sem defeito", e isso vale para todas as aprovações deste
  texto.
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
  apresenta como certificação é a `riscv-arch-test` (*Architectural
  Certification Tests*), não usada aqui.
- **Ambiente próprio do juiz.** O `spec-riscv-test` roda os programas
  oficiais num ambiente sem CSR/ECALL e relinkado em 0.
- **Escopo.** Só monociclo (RV32I e RV32IM); multiciclo e pipeline não foram
  gerados.
- **Métrica de hardware limitada.** Área e Fmax existem só para seis CPUs
  (seção 4.13), uma síntese de cada, e o divisor combinacional do monociclo
  domina o caminho crítico: as CPUs ficam a cerca de 3% umas das outras no
  Fmax e a 5% na área, e nenhuma chega perto do alvo de 100 MHz. Por isso essa métrica não serve, com este
  escopo, para dizer qual modelo gera hardware melhor; também não houve
  comparação com uma CPU otimizada à mão nem medição de potência na placa.
- **`--max-casos-teste` reduzido a 4.** Menos testes de componente do que o
  padrão.
- **Sessão retomada.** A rodada aprovada foi interrompida e retomada 3 vezes,
  duas delas depois de mudanças no gerador; não é uma execução contínua de
  uma única versão do código.

## 8 Trabalhos futuros

Já feito e por isso fora desta lista: RV32IM (seções 4.5 a 4.7), o oráculo
do M no nível da CPU e a checagem de códigos entre blocos (seção 4.11), e o
conserto do laço do juiz que desistia com rodadas sobrando (`cd381bb`,
testado com modelo falso, **sem rodada real**) e a síntese no Quartus das
CPUs RV32IM aprovadas (seção 4.13).

- Repetir numa versão fixa do código, com linha de base: fluxo completo,
  fluxo sem os testes de componente e evolução, ~20 rodadas por braço.
- Spec × modelo, com um modelo mais fraco e uma spec contrafactual (que
  contradiga a memória do modelo num ponto da ISA), para separar spec de
  contaminação (seção 7).
- Rodar a `riscv-arch-test` como terceiro juiz. O README oficial
  (<https://github.com/riscv-non-isa/riscv-arch-test>, que redireciona para
  `github.com/riscv/riscv-arch-test`, ramo padrão `act4`; aberto em
  27/11/2026) diz que os testes agora rodam com o framework ACT4, que
  substitui o RISCOF, marcado como obsoleto (*deprecated*); a integração tem
  de ser feita com o ACT4.
- Mutação em mais blocos e com `--rotulos` e o oráculo do M no laço como
  tratamentos; prova formal de equivalência dos sobreviventes.
- Uma rodada real que exercite o laço do juiz corrigido e a evidência de
  interfaces, de preferência injetando desencontros de propósito.
- Checagem de interfaces que pegue também código igual com significado
  diferente (por exemplo, com testes de integração gerados a partir dos
  contratos dos dois blocos).
- Modelos diferentes por papel (redator, revisor, VHDL, testbench).
- Divisão em vários ciclos (ou pipeline) antes de comparar área e Fmax
  entre modelos, já que no monociclo o divisor domina (seção 4.13); e mais
  de uma semente de síntese.
- Dividir `rvgen/agente.py` em módulos por fase.

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
