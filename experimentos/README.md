# Experimentos

Cada pasta aqui é uma CPU gerada por IA com `python -m rvgen gerar <nome>`,
com tudo o que o gerador registrou. Ficam separadas de `entregas/` (CPUs de
alunos) e de `cpus/` (referências escritas à mão). O método e a discussão dos
resultados estão em [`docs/artigo.md`](../docs/artigo.md).

## Experimentos

| Pasta | Modelo | Alvo | Fluxo | `spec-riscv-test` | `rvverify` | Chamadas | Tokens (entrada / saída) | Custo | Commit |
|---|---|---|---|---|---|---|---|---|---|
| [`luna6_prof_3`](luna6_prof_3/) | `openai/gpt-6-luna` (OpenRouter) | RV32I monociclo | completo, `--max-casos-teste 4` | 40/40 | 24/24 na etapa RV32I (veredito `parcial`) | 78 | 743.978 / 124.821 | cerca de US$ 0,137 | `5068458` |
| [`luna6_im_1`](luna6_im_1/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM monociclo | completo, `--max-casos-teste 4`, `--max-chamadas 150` | 48/48 (8/8 só no M) | não rodado (a etapa RV32M exige generic) | 68 | 740.595 / 115.218 | cerca de US$ 0,132 | `068cc7b` |
| [`luna6_evolui_im_3`](luna6_evolui_im_3/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM, **evoluindo** a `luna6_prof_3`, decomposição livre | `--evoluir-de`, mesmas flags, `--max-chamadas 150`, `--max-blocos` 16 | 48/48 (8/8 só no M) | não rodado | 28 | 380.089 / 52.818 | cerca de US$ 0,064 | este commit |
| [`luna6_evolui_im_2`](luna6_evolui_im_2/) | `openai/gpt-6-luna` (OpenRouter) | RV32IM, **evoluindo** a `luna6_prof_3` | `--evoluir-de`, mesmas flags, `--max-chamadas 150` | 48/48 (8/8 só no M) | não rodado | 26 | 388.021 / 41.988 | cerca de US$ 0,060 | este commit |
| [`luna6_evolui_im_1`](luna6_evolui_im_1/) | `openai/gpt-6-luna` (OpenRouter) | idem | idem | não chegou ao juiz final (teto de 150 chamadas) | — | 150 | 1.940.538 / 131.307 | cerca de US$ 0,26 | este commit |

"Fluxo completo" é `--testes-componentes --gates-componentes
--regressoes-componentes`. Os números são da sessão aprovada
(`sessao-20261104-171911`); as duas rodadas anteriores, que pararam em
defeitos do `rvgen`, não estão versionadas (ver `docs/artigo.md`, seção 4.3).

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

## Novo experimento

```bash
python -m rvgen gerar <nome> --provedor openrouter --modelo openai/gpt-6-luna \
  --testes-componentes --gates-componentes --regressoes-componentes
```

Um nome simples grava em `experimentos/<nome>/`. Uma sessão interrompida (teto
de chamadas, erro, queda do Docker) continua com
`python -m rvgen retomar <nome> <id-da-sessao>`. O veredito exige Linux/WSL2
com GHDL, compilador RISC-V e `riscv-tests`; a imagem `docker/veredito` reúne
tudo (comandos em `docs/artigo.md`, seção Reprodutibilidade).
