# Experimentos

Cada pasta aqui é uma CPU gerada por IA com `python -m rvgen gerar <nome>`,
com tudo o que o gerador registrou. Ficam separadas de `entregas/` (CPUs de
alunos) e de `cpus/` (referências escritas à mão). O método e a discussão dos
resultados estão em [`docs/artigo.md`](../docs/artigo.md).

## Experimentos

| Pasta | Modelo | Alvo | Fluxo | `spec-riscv-test` | `rvverify` | Chamadas | Tokens (entrada / saída) | Custo | Commit |
|---|---|---|---|---|---|---|---|---|---|
| [`luna6_abl_m_completa_1`](luna6_abl_m_completa_1/) … `_4` | `openai/gpt-6-luna` | RV32IM do zero, spec do M **completa** (`it-001`) | completo, `--max-casos-teste 4`, `--max-chamadas 150` | `_1`, `_3`, `_4`: 48/48 (8/8 só no M); `_2` parou na revisão do contrato | não rodado | 70 / 15 / 67 / 64 | ver `docs/artigo.md` 4.9 | US$ 0,126 / 0,039 / 0,125 / 0,121 | este commit |
| [`luna6_abl_m_reduzida_1`](luna6_abl_m_reduzida_1/) … `_4` | `openai/gpt-6-luna` | RV32IM do zero, spec do M **reduzida** à codificação (`it-002`) | idem | `_2`, `_3`: 48/48 (8/8 só no M); `_4`: 1/48; `_1` parou no defeito 6 | não rodado | 44 / 84 / 84 / 132 | ver `docs/artigo.md` 4.9 | US$ 0,080 / 0,152 / 0,160 / 0,327 | este commit |
| [`luna6_prof_3`](luna6_prof_3/) | `openai/gpt-6-luna` (OpenRouter) | RV32I monociclo | completo, `--max-casos-teste 4` | 40/40 | 24/24 na etapa RV32I (veredito `parcial`) | 78 | 743.978 / 124.821 | cerca de US$ 0,137 | `5068458` |
| [`luna6_im_1`](luna6_im_1/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM monociclo | completo, `--max-casos-teste 4`, `--max-chamadas 150` | 48/48 (8/8 só no M) | não rodado (a etapa RV32M exige generic) | 68 | 740.595 / 115.218 | cerca de US$ 0,132 | `068cc7b` |
| [`qwen38_cluster_prof_1`](qwen38_cluster_prof_1/) | `nvidia/Qwen3.8-Flash-Next-FP4-Local` (vLLM no cluster) | RV32I monociclo | completo | não chegou ao juiz (servidor vLLM deu timeout) | — | 2 | — | US$ 0 (local) | este commit |
| [`qwen38_cluster_prof_2`](qwen38_cluster_prof_2/) | idem | RV32I monociclo | completo | não chegou ao juiz (servidor vLLM recusou a conexão) | — | 3 | — | US$ 0 (local) | este commit |
| [`sol6_evolui_im_1`](sol6_evolui_im_1/) | `openai/gpt-6-sol` | RV32IM, evoluindo a `luna6_prof_3` | idem `_5` (código de 13/11) | 48/48 (8/8 só no M) | não rodado | 55 | 642.594 / 50.811 | US$ 1,79 | este commit |
| [`carbon4_evolui_im_1`](carbon4_evolui_im_1/) | `google/gemini-4-carbon` | idem | idem | 48/48 (8/8 só no M) | não rodado | 38 | 637.481 / 153.150 | US$ 2,81 | este commit |
| [`sonnet55_evolui_im_2`](sonnet55_evolui_im_2/) | `anthropic/claude-sonnet-5.5` | idem | idem | 48/48 (8/8 só no M) | não rodado | 116 | 2.830.786 / 267.544 | US$ 8,34 | este commit |
| [`sonnet55_evolui_im_1`](sonnet55_evolui_im_1/) | `anthropic/claude-sonnet-5.5` | idem | idem | parou na revisão do contrato (defeito do leitor, corrigido) | — | 10 | 246.244 / 60.958 | US$ 1,10 | este commit |
| [`luna6_evolui_im_5`](luna6_evolui_im_5/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM, **evoluindo** a `luna6_prof_3`, decomposição livre **sem** a regra do topo | idem `_3` + `--permitir-conta-no-topo` | 48/48 (8/8 só no M) | não rodado | 38 | 501.848 / 56.953 | cerca de US$ 0,079 | este commit |
| [`luna6_evolui_im_4`](luna6_evolui_im_4/) | idem | idem | idem | não passou do plano (validador recusou portas em texto) | — | 2 | — | — | este commit |
| [`luna6_evolui_im_3`](luna6_evolui_im_3/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM, **evoluindo** a `luna6_prof_3`, decomposição livre | `--evoluir-de`, mesmas flags, `--max-chamadas 150`, `--max-blocos` 16 | 48/48 (8/8 só no M) | não rodado | 28 | 380.089 / 52.818 | cerca de US$ 0,064 | este commit |
| [`luna6_evolui_im_2`](luna6_evolui_im_2/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM, **evoluindo** a `luna6_prof_3` | `--evoluir-de`, mesmas flags, `--max-chamadas 150` | 48/48 (8/8 só no M) | não rodado | 26 | 388.021 / 41.988 | cerca de US$ 0,060 | este commit |
| [`luna6_evolui_im_1`](luna6_evolui_im_1/) | `openai/gpt-6-luna` (OpenRouter) | idem | idem | não chegou ao juiz final (teto de 150 chamadas) | — | 150 | 1.940.538 / 131.307 | cerca de US$ 0,26 | este commit |

"Fluxo completo" é `--testes-componentes --gates-componentes
--regressoes-componentes`. Os números são da sessão aprovada
(`sessao-20261104-171911`); as duas rodadas anteriores, que pararam em
defeitos do `rvgen`, não estão versionadas (ver `docs/artigo.md`, seção 4.3).

### `luna6_abl_m_*` (ablação da spec do M, 23/11/2026)

A pergunta: os casos especiais e os exemplos do `riscv-rv32m.md` são o que
faz a IA acertar o M? Três rodadas de cada variante, do zero, com o luna 6
(`docs/artigo.md`, seção 4.9). Resposta com este modelo: não. Todas as CPUs
que chegaram ao juiz trataram divisão por zero e overflow, com ou sem a
spec completa, e as cinco aprovadas passaram 8/8 no M. A `reduzida_4`
reprovou (1/48) porque a `control_unit` e a `alu` combinaram códigos
`alu_op` diferentes (o `LUI` virava `MUL`), e o laço do juiz não a corrigiu.
A `completa_2` parou porque o revisor achou contradições reais no contrato
do `cpu` que o redator não resolveu em 3 rodadas; a `reduzida_1` parou num
defeito do gerador (regressão com vários testes), corrigido. A `completa_3`
e a `reduzida_3` foram retomadas uma vez, com o mesmo código, depois de uma
queda da sessão do assistente.

### Mutação dos blocos do M

`<cpu>/mutacao/<bloco>.json` em `luna6_evolui_im_5` (`muldiv`),
`luna6_evolui_im_3` (`rv32m_unit`), `sol6_evolui_im_1` (`m_unit`),
`carbon4_evolui_im_1` (`muldiv_unit`) e `sonnet55_evolui_im_2`
(`multiplier`, `divider`) (`docs/artigo.md`, seção 4.10): os testes de
componente da IA mataram de 19% (luna 6) a 88% (Gemini) dos mutantes, o juiz
de 76% a 83%, e o que escapou de tudo está nas guardas de overflow da
divisão. Para refazer (no Docker do veredito; não chama IA):

```bash
python3 -m rvgen mutacao experimentos/luna6_evolui_im_5 --bloco muldiv --oraculo rvgen/oraculo_m_cpu.py
```

### Mutação dos blocos fora do M

Arquivos novos de 27/11/2026, sem oráculo (ele só cobre o M), em
`docs/artigo.md`, seção 4.10, tabela "Blocos fora do M":

- `luna6_evolui_im_5/mutacao/`: `alu.json`, `register_file.json`,
  `immediate_generator.json`, `decoder.json`, `cpu.json`;
- `luna6_im_1/mutacao/`: `execution_unit.json`, `load_store_unit.json`,
  `register_file.json`, `immediate_generator.json`, `cpu.json`.

Nos 559 mutantes viáveis, os testes da IA (bloco ou `cpu`) mataram 160 (29%)
e o juiz 487 (87%); 64 passaram por tudo e ficam **não classificados** (sem
oráculo não dá para dizer se são equivalentes). Os blocos `decoder` e `cpu`
do `luna6_evolui_im_3` não foram rodados (limite de 10 h). Para refazer um
bloco (no Docker do veredito, montando o repositório em `/repo`; não chama
IA; de 25 min a 5,5 h por bloco nesta máquina com duas filas em paralelo):

```bash
python3 -m rvgen mutacao experimentos/luna6_evolui_im_5 --bloco alu --paralelo 4
python3 -m rvgen mutacao experimentos/luna6_im_1 --bloco execution_unit --paralelo 4
```

O trabalho fica em `out/mutacao/<cpu>/<bloco>/` (ignorado pelo git); o
`src/` da CPU não é alterado.

### Checagens sem IA em qualquer CPU

```bash
python3 -m rvgen oraculo-m luna6_im_1 sol6_evolui_im_1   # M em 256 pares de borda, na entidade cpu
python -m rvgen interfaces                               # codigos entre blocos, todas as CPUs
```

As 12 CPUs RV32IM aprovadas passam no oráculo; a checagem de interfaces
acusa só a `luna6_abl_m_reduzida_4` (`docs/artigo.md`, seção 4.11).

### `luna6_prof_3`

Primeira CPU RV32I gerada pelo `openai/gpt-6-luna` aprovada pelo juiz do
`rvgen`: 40/40 no `spec-riscv-test` e 24/24 na etapa RV32I do `rvverify`
(veredito `parcial` do `rvverify`, que só aprova a suíte completa; a etapa
RV32M exige um generic que o contrato atual não tem). A IA dividiu a CPU em `immediate_generator`, `register_file`, `alu`,
`decoder` e `cpu` (647 linhas de VHDL em `src/`). Passou em 40/40 programas
`rv32ui` do `spec-riscv-test` com 0 iterações de correção. O `cpu.toml` foi
escrito depois da geração, só para rodar o `rvverify`; ele não
faz parte do que o `rvgen` produz. A sessão foi retomada 3 vezes (eventos
`retomada` no `sessao.jsonl`).

### `luna6_im_1`

Primeira CPU RV32IM gerada pela IA (06/11/2026), com as specs da iteração
[`iteracoes/it-001`](../iteracoes/it-001/): iguais a `specs/`, só com a linha
de declaração `- RV32IM single cycle`, o que junta
[`riscv-rv32m.md`](../specs/riscv-rv32m.md) ao prompt. A IA dividiu a CPU em
`immediate_generator`, `register_file`, `execution_unit` (ALU e M juntos),
`load_store_unit` e `cpu` (598 linhas de VHDL). Passou em 48/48 programas
(40 `rv32ui` + 8 `rv32um`) com 0 iterações de correção do VHDL, numa
execução só, sem retomada. Rodando de novo por fora, só os 8 programas do M:
8/8. Desta vez 2 dos 49 testes de componente falharam e a triagem culpou o
testbench nas duas vezes (2 chamadas `triagem_componente` e 2
`correcao_testbench`). A revisão recusou uma vez a especificação do `cpu`.
40 das 68 chamadas foram na expansão de testes.

### `qwen38_cluster_prof_1` e `_2` (interrompidas)

Duas tentativas de 12/11/2026 com um modelo local, o
`nvidia/Qwen3.8-Flash-Next-FP4-Local`, servido por vLLM num servidor do
cluster (`--provedor vllm`). As duas pararam por falha do servidor, não do
`rvgen` nem do modelo, ainda escrevendo o contrato do primeiro bloco (nenhum
VHDL foi escrito): a `_1` depois de 2 chamadas, por tempo esgotado na
resposta; a `_2` depois de 3 chamadas, com o servidor recusando a conexão
mesmo após as 3 tentativas automáticas. Com o servidor no ar, continuam com
`python -m rvgen retomar`. Esforço de raciocínio do vLLM:
`RVGEN_VLLM_REASONING_EFFORT` (`low`, `medium` ou `high`) no `.env`.

### `luna6_evolui_im_5` (e `luna6_evolui_im_4`)

A pergunta do professor: só liberar a decomposição, sem proibir conta no
topo, já faria a IA criar o módulo novo? Mesma evolução da `_3`, com
`--permitir-conta-no-topo`. Sim: a IA criou o bloco `muldiv` (85 linhas),
mudou `decoder` (sinaliza o M) e `cpu` (só integra, sem multiplicação,
divisão nem resto) e manteve `alu`, `register_file` e `immediate_generator`
iguais. 48/48 (8/8 só no M), 38 chamadas, 52 de 52 testes de componente. A
`_4` parou no plano por um defeito do validador (portas em um texto só,
`"a; b"`), corrigido antes da `_5`.

### `luna6_evolui_im_3`

A mesma evolução depois de liberar a decomposição (o plano pode manter,
mudar, criar, dividir, juntar, renomear e remover blocos), proibir conta no
topo e trocar o limite fixo de 8 blocos por `--max-blocos`. A IA criou um
bloco novo `rv32m_unit` (91 linhas) com as 8 operações do M e seus casos
especiais, mudou só o `cpu` (que agora apenas integra) e manteve `alu`,
`decoder`, `register_file` e `immediate_generator` byte a byte iguais. 48/48
(8/8 só no M), 28 chamadas, 0 correções de VHDL; 44 de 45 testes de
componente (um caso novo do `rv32m_unit` falhou, a triagem culpou o teste e o
corrigiu).

### `luna6_evolui_im_2` (e `luna6_evolui_im_1`)

Plano ainda restrito ("a menor mudança", sem criar blocos de preferência,
limite de 8): a IA pôs o M dentro do `cpu`. Passou no juiz, mas é a
decomposição que a `luna6_evolui_im_3` corrige.


A mesma mudança de RV32I para RV32IM, mas **evoluindo** a CPU aprovada
`luna6_prof_3` em vez de gerar do zero (`rvgen gerar --evoluir-de`, specs de
`iteracoes/it-001`). Antes de mudar, a linha de base deu 25/25 testes de
componente e 40/40 no juiz RV32I. O plano da IA
(`.rvgen/sessao-*/evolucao/plano.md`) mudou o `decoder` e o `cpu`; `alu`,
`register_file` e `immediate_generator` ficaram byte a byte iguais. Passou em
48/48 (8/8 só no M) com 26 chamadas, 0 correções de VHDL e 43 de 43 testes de
componente, contra 68 chamadas gerando do zero (`luna6_im_1`).

A primeira tentativa (`luna6_evolui_im_1`) parou no teto de 150 chamadas: o
pedido de caso de teste mandava usar `assemble_rv32i` e o validador de uma
CPU RV32IM só aceitava `assemble_rv32im`, e 30 casos do `decoder` foram
recusados em sequência. O defeito valia para qualquer geração RV32IM com um
bloco que recebe a instrução; foi corrigido antes da segunda tentativa. A
pasta fica como evidência; o plano dela (que criava um bloco `rv32m`) está em
`.rvgen/sessao-*/evolucao/plano.md`.

## O que tem numa pasta de experimento

```text
<nome>/
  architecture.json        instruções documentadas pela IA e a decomposição em blocos
  src/*.vhd                o VHDL gerado (a IA só escreve aqui)
  cpu.toml                 opcional, escrito à mão para rodar o rvverify
  .rvgen/sessao-<id>/      uma pasta por sessão do gerador
```

## Como ler uma sessão

Dentro de `.rvgen/sessao-<id>/`:

| Arquivo ou pasta | O que é |
|---|---|
| `sessao.jsonl` | Diário completo, um evento JSON por linha. Os eventos `llm` trazem `fase`, prompt (`mensagens`), `resposta`, `tokens_entrada`, `tokens_saida` e `segundos`; `inicio` traz as opções da geração; `retomada`, `especificacao_reprovada`, `teste_componente`, `componente_aprovado` e `spec-riscv-test` contam o resto da história; `fim` repete o resultado. |
| `resultado.json` | Resumo final: veredito, placar, iterações, chamadas, tokens, provedor, modelo e caminho do relatório. |
| `contrato.txt`, `contrato-testes.txt`, `testes.md` | Prompts de sistema usados (o do VHDL e o dos testbenches; nos eventos `llm` aparecem como `@contrato.txt` e `@contrato-testes.txt`) e a cópia das regras de teste. |
| `component_specs/<bloco>.comp_spec.txt` | Contrato de cada bloco, já aprovado pelo revisor. |
| `planos_incrementais/<bloco>.md` | Plano de casos de teste de cada bloco. |
| `testes/test_<bloco>.py` | Testbench cocotb final de cada bloco. |
| `testes_aprovados/`, `testes_candidatos/`, `testes_casos/`, `testes_resultados/` | Casos incrementais propostos, aprovados e os resultados de cada execução. |
| `componentes_aprovados/<bloco>.json` | Hash do VHDL no momento em que o bloco foi congelado e os testes que ele passou. |
| `hierarquia/`, `diagnosticos/` | Inventário da hierarquia da CPU integrada e testes de diagnóstico. |
| `build/`, `sim/` | Saída do GHDL e do cocotb por componente e por caso. **Não versionadas** (`.gitignore`): ficam só na máquina que gerou a CPU. |
| `spec-riscv-test/fumaca/`, `spec-riscv-test/suite/` | Execuções do juiz: os ELFs compilados em `programs/` (com o `.build.log` de cada um), `config.json`, `report.json` e `sim.log` por programa, e o `report.json` geral. O veredito está em `spec-riscv-test/suite/report.json`. A simulação do juiz não é versionada. |

**Atenção ao `resultado.json` de sessões retomadas.** Os campos `chamadas`,
`tokens_entrada`, `tokens_saida` e `segundos` do `resultado.json` contam só a
última execução. O de `luna6_prof_3` mostra `"chamadas": 2`, não 78. Desde a
correção do defeito 5 do artigo, o `resultado.json` de uma sessão retomada
traz também um bloco `sessao` com os totais da sessão inteira, e o
`rvgen comparar` e o app de iterações mostram esses totais (num
`resultado.json` antigo, sem o bloco, eles somam os eventos `llm` do
`sessao.jsonl`). O `sessao.jsonl` é a fonte completa; a soma por fase sai
assim:

```bash
python -c "import json,collections,sys; c=collections.Counter(); t=[0,0]
for l in open(sys.argv[1],encoding='utf-8'):
  d=json.loads(l)
  if d['evento']=='llm': c[d['fase']]+=1; t[0]+=d['tokens_entrada'] or 0; t[1]+=d['tokens_saida'] or 0
print(sum(c.values()),'chamadas',t[0],'entrada',t[1],'saida'); print(c.most_common())" \
  experimentos/luna6_prof_3/.rvgen/sessao-20261104-171911/sessao.jsonl
```

## Como comparar

```bash
python -m rvgen comparar                        # a sessão mais recente de cada experimento
python -m rvgen comparar experimentos/luna6_prof_3 --todas
python -m rvgen comparar --markdown experimentos/COMPARACAO.md
python -m rvgen comparar --sem-rede             # sem buscar preços; custo sai como ?
```

Para ver **onde** as chamadas, o tempo e as falhas foram gastos, por grupo de
fases (planejamento, contratos, VHDL, testes, correção, juiz):

```bash
python -m rvgen telemetria experimentos/luna6_evolui_im_5 experimentos/sol6_evolui_im_1
python -m rvgen telemetria experimentos/luna6_prof_3 --detalhado   # uma linha por fase do rvgen
python -m rvgen telemetria --markdown telemetria.md                 # todos os experimentos
```

A telemetria inclui sessões interrompidas (mostra onde pararam) e conta, além
de chamadas e tokens, o tempo de simulação, as falhas de simulação, as
recusas do validador e do revisor e os erros do provedor (`docs/artigo.md`,
seção 4.8).

`comparar` só lê os registros da sessão (`resultado.json`, o relatório do
`spec-riscv-test` e, numa sessão retomada sem o bloco `sessao`, o
`sessao.jsonl`); não roda modelo nem GHDL. Numa sessão retomada, chamadas,
tokens e tempo são da sessão inteira, e o tempo passa a ser o tempo de
resposta do modelo somado (para `luna6_prof_3`: 78 chamadas, 743978+124821
tokens, 23,6 min). O custo é uma estimativa: tokens registrados vezes o preço
público do OpenRouter no dia da comparação.

Para rodar os juízes de novo sobre uma CPU daqui (Linux/WSL2, imagem de
`docker/veredito/`; variantes para Git Bash e PowerShell em
[`docker/veredito/README.md`](../docker/veredito/README.md)):

```bash
docker build -t rvgen-veredito docker/veredito
docker run --rm -v "$PWD:/repo" rvgen-veredito \
  spec-riscv-test --cpu experimentos/luna6_prof_3 --riscv-tests /opt/riscv-tests --out out/luna6_prof_3
docker run --rm -v "$PWD:/repo" rvgen-veredito \
  python3 -m rvverify experimentos/luna6_prof_3 --etapa rv32i
```

## Comparar as CPUs no Quartus (área, Fmax, potência)

O juiz só diz se a CPU está certa (todas as da comparação de modelos dão
48/48). Para saber qual é **melhor em hardware**, sintetize no Quartus. As
cinco CPUs RV32IM abaixo já têm `cpu.toml` (fontes na ordem de compilação,
conferida no GHDL) e rodam com o `quartus_testing`.

No Linux, da raiz do repositório (Python 3.11+ e Docker rodando):

```bash
git pull
docker pull gabrielgalazzi/imagens_projeto_descomp:25.1   # imagem do Quartus, ~8 GB, uma vez só
for cpu in luna6_evolui_im_5 sol6_evolui_im_1 carbon4_evolui_im_1 sonnet55_evolui_im_2 luna6_im_1; do
    python3 quartus_testing/quartus_cpu_check.py experimentos/$cpu
done
```

| Pasta | Modelo que gerou | Bloco do M |
|---|---|---|
| `luna6_evolui_im_5` | `openai/gpt-6-luna` (evoluindo a RV32I) | `muldiv` |
| `sol6_evolui_im_1` | `openai/gpt-6-sol` (evoluindo a RV32I) | `m_unit` |
| `carbon4_evolui_im_1` | `google/gemini-4-carbon` (evoluindo a RV32I) | `muldiv_unit` |
| `sonnet55_evolui_im_2` | `anthropic/claude-sonnet-5.5` (evoluindo a RV32I) | `multiplier` + `divider` |
| `luna6_im_1` | `openai/gpt-6-luna` (do zero) | dentro de `execution_unit` |

O resultado de cada CPU fica em `quartus_testing/resultados/<pasta>/relatorio.md`
(compila?, Fmax, ALMs/LUTs/registradores/DSP e potência estimada), que **não é
versionado** (`quartus_testing/.gitignore` ignora `resultados/`). O alvo padrão
é 100 MHz (`--periodo-ns 10`). Os `cpu.toml` não têm `rv32m_generic` porque o
M é fixo (sem generic): use o `--isa padrao`, que é o padrão. Detalhes do
script em [`quartus_testing/how_to_use.md`](../quartus_testing/how_to_use.md).
O gabarito RV32IM também tem `cpu.toml` e roda do mesmo jeito:
`python3 quartus_testing/quartus_cpu_check.py cpus/rv32im_gabarito`.

**Resultado de 27/11/2026** (Windows, Python 3.12 do host e Docker Desktop;
Quartus 25.1std.0 Lite; Cyclone V `5CEBA4F23C7`; uma síntese por CPU, semente
padrão). A imagem ocupou 22,4 GB em disco (8,12 GB de conteúdo, `docker images`).
Todas compilam e nenhuma atende os 100 MHz; detalhes e ressalvas na seção 4.13
do [`docs/artigo.md`](../docs/artigo.md).

| Pasta | Fmax (MHz) | ALMs | ALUTs | Registradores | DSP | Potência estimada (mW) | Compilação (min) |
|---|---|---|---|---|---|---|---|
| `luna6_evolui_im_5` | 9,87 | 4.071 | 6.655 | 1.023 | 9 | 836 | 63,5 |
| `sol6_evolui_im_1` | 9,79 | 4.068 | 6.633 | 1.023 | 9 | 868 | 43,7 |
| `carbon4_evolui_im_1` | 10,02 | 4.095 | 6.616 | 1.023 | 9 | 827 | 57,9 |
| `sonnet55_evolui_im_2` | 10,01 | 3.996 | 6.479 | 1.023 | 3 | 809 | 50,3 |
| `luna6_im_1` | 10,09 | 4.202 | 6.855 | 1.023 | 9 | 897 | 53,7 |
| `cpus/rv32im_gabarito` | 9,90 | 4.027 | 6.503 | 1.023 | 3 | 783 | 45,4 |

Fontes, em `quartus_testing/resultados/<pasta>/quartus_output_padrao/`: Fmax
de `compilation/fmax.log`; ALMs, registradores e DSP de
`reports/padrao.fit.summary`; ALUTs de `reports/resources.json`; potência de
`reports/padrao.pow.summary`; tempo de `duracao_compilacao_s` no
`relatorio.json`. Os tempos foram medidos com a mutação rodando ao mesmo
tempo na máquina (estão inflados); conte com cerca de 45 a 65 minutos por
CPU, não segundos. Nas seis, o caminho crítico passa pelo divisor
combinacional (`reports/critical_path.log`), por isso o Fmax quase não muda
entre os modelos.

## Novo experimento

```bash
python -m rvgen gerar <nome> --provedor openrouter --modelo openai/gpt-6-luna \
  --testes-componentes --gates-componentes --regressoes-componentes
```

Com `--rotulos`, contratos e testes citam os rótulos `CK-*` do catálogo
`rotulos.md` da pasta de specs (a iteração `it-003` é a `it-001` com o
catálogo), conferidos sem IA; a sessão ganha `rotulos_cobertura.json`.

Um nome simples grava em `experimentos/<nome>/`. Uma sessão interrompida (teto
de chamadas, erro, queda do Docker) continua com
`python -m rvgen retomar <nome> <id-da-sessao>`. O veredito exige Linux/WSL2
com GHDL, compilador RISC-V e `riscv-tests`; a imagem `docker/veredito` reúne
tudo (comandos em `docs/artigo.md`, seção Reprodutibilidade).
