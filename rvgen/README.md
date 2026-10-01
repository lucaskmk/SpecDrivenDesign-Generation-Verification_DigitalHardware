# rvgen — gerador de CPUs RISC-V por agente

O `rvgen` escreve uma CPU RISC-V em VHDL com um modelo de linguagem — local
(Ollama) ou externo (OpenRouter) — e a submete ao **mesmo** `rvverify` que
julga a CPU de um aluno, corrigindo a partir do diagnóstico até o veredito.
Ele é cliente do validador, nunca o contrário: o modelo nunca vê o
validador, nunca escreve fora de `src/` e nunca decide se passou.

Requisitos: FR-RV-43 a FR-RV-50 e NFR-RV-07 (`specs/spec.md`). Arquitetura:
`specs/plan.md`, seção 9. Decisão: ADR-018 (`specs/decisions.md`).

A primeira parte é o **passo a passo** de uso. A segunda (seções 1 a 10) é
o **modelo dos prompts**: o que o agente manda ao modelo em cada fase.

---

## Passo a passo

Os comandos são para o terminal (PowerShell no Windows), na raiz do
repositório, um de cada vez.

### Passo 1 — preparar a máquina (uma vez só)

1. Abra o **Docker Desktop** e espere aparecer "Engine running". É nele que
   o GHDL roda: o Windows não tem GHDL nem cocotb, e o projeto não aceita
   dizer que uma CPU passou sem simular de verdade.
2. Baixe a imagem do validador e dê a ela o nome local que o projeto usa:
   ```bash
   docker pull gabrielgalazzi/imagens_projeto_descomp:spechdl-latest
   ```
   ```bash
   docker tag gabrielgalazzi/imagens_projeto_descomp:spechdl-latest spechdl-toolchain
   ```
3. Confira tudo. O `preparar` instala o Ollama, sobe o servidor e baixa o
   modelo local, **perguntando antes** de instalar ou baixar qualquer coisa:
   ```bash
   python -m rvgen preparar
   ```
   Ele precisa terminar com "Tudo pronto". Para só conferir, sem mudar nada,
   use `python -m rvgen preparar --verificar`.

### Passo 2 — escolher a IA

**IA local (Ollama)** — é o padrão; não precisa de chave nem de internet
depois do download. O modelo é escolhido pela memória da sua GPU:

| perfil | modelo | download | quando |
|---|---|---|---|
| `leve` | `qwen2.5-coder:7b` | 4,68 GB | GPU com menos de 10 GB |
| `padrao` | `qwen2.5-coder:14b` | 8,99 GB | GPU de 10 a 23 GB |
| `forte` | `qwen3-coder:30b` | 18,56 GB | GPU de 24 GB ou mais (roda com parte na RAM) |

Para trocar, baixe o outro modelo com o `preparar` e passe `--perfil` (ou
`--modelo` com qualquer modelo do Ollama) ao gerar:

```bash
python -m rvgen preparar --perfil forte
```

**IA externa (OpenRouter)** — qualquer modelo do catálogo em
<https://openrouter.ai/models> (GPT, Claude, Gemini, Qwen...), pago por uso.

1. Crie uma chave em <https://openrouter.ai/keys>.
2. Crie o arquivo `.env` na raiz do repositório (copie o `.env.example`),
   ponha a chave e **salve** o arquivo:
   ```text
   OPENROUTER_API_KEY=sk-or-...
   SPECHDL_LLM_MODEL=openai/gpt-5.6-luna
   ```
   O `.env` nunca vai para o Git (está no `.gitignore`); o `.env.example`
   vai, então **não ponha a chave nele**.
3. Confira que a chave foi lida (a linha `info` do `preparar` diz
   "OPENROUTER_API_KEY definida"). Depois, ao gerar, use
   `--provedor openrouter`. `SPECHDL_LLM_MODEL` é o modelo externo padrão;
   `--modelo` escolhe outro na hora, por exemplo
   `--modelo openai/gpt-6-luna` ou `--modelo anthropic/claude-...`, com o
   nome exato do catálogo.

### Passo 3 — descrever a CPU

A CPU é descrita por **dois parâmetros** e o resto é fixado pelo contrato
do validador (seção 2), o mesmo que um aluno recebe:

| parâmetro | valores | o que muda |
|---|---|---|
| `--tipo` | `monociclo` | uma instrução por ciclo; a mais simples |
| | `multiciclo` | máquina de estados, de 3 a 5 ciclos por instrução |
| | `pipeline` | 5 estágios, forwarding, stall de load-use, flush em salto |
| `--isa` | `rv32i` | só a base inteira (veredito final: INCOMPLETO, porque a etapa M é pulada) |
| | `rv32im` | base + multiplicação e divisão (veredito final: APROVADO ou REPROVADO) |

O que **já vem fixo** e o modelo não escolhe: o top-level `cpu_top` com
`clk`/`rst` e os generics `ROM_INIT_FILE`, `ROM_SIZE_WORDS` e
`RV32M_ENABLE`; as memórias e a `mul_div_unit` fornecidas por
`cpus/rv32i_pipeline/src/`; o mapa de memória; os nomes dos sinais que o
testbench lê; e o `cpu.toml`. O que **o modelo decide**: a divisão em
blocos (`architecture.json`) e todo o VHDL de `src/`.

**Descrever em texto livre** (opcional, além do tipo e da ISA). Diga o que
você quer da CPU, em qualquer língua:

```bash
python -m rvgen gerar ia_mono_desc --tipo monociclo --isa rv32im --descricao "Banco de registradores com reset síncrono. Gerador de imediatos separado do decodificador."
```

Para um texto longo, escreva num arquivo e use `--descricao-arquivo descricao.txt`.
Como a descrição é tratada (FR-RV-52, ADR-020):

- ela vai para os pedidos de decomposição, escrita e correção, **abaixo do
  contrato**: se pedir algo que o contrato fixa (outro top-level, outra
  memória, outros nomes), vale o contrato, porque é o que o validador julga;
- na decomposição, o modelo mapeia cada item pedido para o bloco que o
  atende, no campo `requests` do `architecture.json`;
- fica gravada em `experimentos/<nome>/descricao.md` e na sessão, e a
  comparação marca o experimento com `+descricao`;
- **não é verificada**: o veredito continua julgando só o contrato. Que a
  CPU "tem reset síncrono" é declaração do modelo; para ter certeza, leia o
  VHDL.

Opções que mudam como o agente trabalha:

| opção | efeito |
|---|---|
| `--iteracoes N` | máximo de correções antes do veredito (padrão 12) |
| `--exemplo cpus/rv32i_monociclo` | mostra ao modelo o VHDL de uma CPU de referência; suba `RVGEN_NUM_CTX` para `32768` no `.env` |
| `--forcar` | sobrescreve os arquivos gerados numa pasta que já existe |

Para ver os tipos e as ISAs aceitas: `python -m rvgen tipos`. Outra ISA
(C, A, Zicsr...) exige primeiro estender o validador.

### Passo 4 — gerar

Cada geração é um **experimento** e vai para uma pasta própria em
[`experimentos/`](../experimentos/) — separada de `entregas/`, que é das
CPUs de alunos (ADR-019). Basta dar um nome; ponha o modelo no nome, para a
comparação ficar legível:

```bash
python -m rvgen gerar ia_mono_qwen14b --tipo monociclo --isa rv32im
```
```bash
python -m rvgen gerar ia_mono_luna --tipo monociclo --isa rv32im --provedor openrouter --modelo openai/gpt-5.6-luna
```

O agente decompõe, escreve um arquivo por vez, roda o `rvverify` no Docker,
corrige a partir dos erros e termina com o veredito, as iterações, os tokens
e o tempo. Com modelo local de 14B, conte de 20 minutos a mais de uma hora;
com um modelo externo, alguns minutos. Rode no seu terminal: pelo terminal
do Claude aparecem janelas piscando.

O resultado fica em (detalhe em [`experimentos/README.md`](../experimentos/README.md)):

| caminho | o que é |
|---|---|
| `experimentos/<nome>/src/*.vhd` | o VHDL gerado |
| `experimentos/<nome>/architecture.json` | a divisão em blocos, com justificativa |
| `experimentos/<nome>/cpu.toml` | o manifesto (gerado sem IA) |
| `experimentos/<nome>/.rvgen/sessao-*/resultado.json` | veredito, placar, iterações, tokens, tempo, modelo |
| `experimentos/<nome>/.rvgen/sessao-*/sessao.jsonl` | todos os prompts e respostas (seção 8) |

### Passo 5 — testar de novo, com o validador sozinho

O veredito do `gerar` já é do `rvverify`, mas dá para rodar o validador
direto sobre qualquer CPU — gerada por IA, feita à mão ou de referência:

```bash
docker run --rm -v "${PWD}:/job" spechdl-toolchain python3 -m rvverify experimentos/ia_mono_qwen14b --sem-cor
```

Para guardar o log do GHDL de cada caso (`sim.log`):

```bash
docker run --rm -v "${PWD}:/job" spechdl-toolchain python3 -m rvverify experimentos/ia_mono_qwen14b --sem-cor --workdir experimentos/ia_mono_qwen14b/report
```

Para ver como é uma aprovação, valide as CPUs de referência:

```bash
docker run --rm -v "${PWD}:/job" spechdl-toolchain python3 -m rvverify cpus/ --sem-cor
```

Como ler o veredito: **APROVADO** = passou nas duas etapas (RV32I e RV32IM);
**REPROVADO** = algum caso falhou (o relatório mostra requisito, entrada,
esperado e obtido); **INCOMPLETO** = a etapa RV32IM foi pulada (normal com
`--isa rv32i`); **PARCIAL** = rodou só parte da suíte com `--casos`.

### Passo 6 — comparar duas CPUs geradas

**6.1 Gere as duas com a mesma descrição.** Mesmo `--tipo`, mesma `--isa`,
mesmo `--iteracoes`; só o modelo muda, cada um no seu experimento (passo 4).
Por exemplo, o modelo local contra o GPT:

```bash
python -m rvgen gerar ia_mono_qwen14b --tipo monociclo --isa rv32im
```
```bash
python -m rvgen gerar ia_mono_luna --tipo monociclo --isa rv32im --provedor openrouter --modelo openai/gpt-5.6-luna
```

**6.2 Ponha lado a lado.** Sem argumento, compara todos os experimentos de
`experimentos/` (a sessão mais recente de cada um); com pastas, só elas:

```bash
python -m rvgen comparar
```
```bash
python -m rvgen comparar experimentos/ia_mono_qwen14b experimentos/ia_mono_luna
```

O que cada coluna diz, e de onde vem:

| coluna | significado | fonte |
|---|---|---|
| `veredito` | APROVADO, REPROVADO, INCOMPLETO | relatório final do `rvverify` |
| `RV32I` | casos da base que passaram (de 24), ou "nao compilou" | relatório final, etapa `rv32i` |
| `RV32IM` | casos da extensão M (de 11); "pulada" quando a base reprovou (FR-RV-11) | relatório final, etapa `rv32m` |
| `iteracoes` | correções usadas (de `--iteracoes`) | `resultado.json` |
| `chamadas` | chamadas ao modelo, somando todas as fases | `resultado.json` |
| `tokens` | entrada + saída, somando todas as chamadas | `resultado.json` |
| `tempo` | do início ao veredito | `resultado.json` |
| `custo` | **estimativa**: tokens × preço público do OpenRouter no dia; local = 0 | preço lido do catálogo do OpenRouter |

Nenhum número é re-medido: tudo sai dos arquivos da sessão. Só o custo não
estava registrado, por isso vem sempre rotulado como estimativa. Com
`--sem-rede`, o custo de modelo externo sai `?`; com `--todas`, entram todas
as sessões de cada experimento, não só a última.

**6.3 Guarde a tabela para o relatório.** A mesma tabela, em Markdown:

```bash
python -m rvgen comparar --markdown experimentos/COMPARACAO.md
```

**6.4 Olhe além da tabela.** Duas CPUs com o mesmo veredito podem ser bem
diferentes; para comparar o hardware e o processo:

- **a arquitetura**: abra o `architecture.json` de cada uma e veja quantos
  blocos cada modelo propôs e como justificou;
- **o código**: compare os `src/*.vhd`, por exemplo o top das duas:
  ```bash
  git diff --no-index experimentos/ia_mono_qwen14b/src/cpu_top.vhd experimentos/ia_mono_luna/src/cpu_top.vhd
  ```
- **onde cada uma falha**: rode o validador nas duas (passo 5) e leia o
  diagnóstico dos casos reprovados: requisito, entrada, esperado, obtido e
  sugestão do bloco a revisar;
- **onde o modelo travou**: liste as fases da sessão, com tokens e tempo de
  cada chamada (troque `<sessao>` pelo nome da pasta):
  ```bash
  python -c "import json,sys; [print(e['fase'], e['alvo'], e['tokens_saida'], e['segundos'], e.get('temperatura')) for e in map(json.loads, open(sys.argv[1], encoding='utf-8')) if e['evento']=='llm']" experimentos/ia_mono_qwen14b/.rvgen/<sessao>/sessao.jsonl
  ```

**6.5 Para a comparação ser justa:**

- mesmo tipo, mesma ISA e mesmo `--iteracoes` nas duas;
- o mesmo prompt: não mude o código do `rvgen` entre as gerações. O
  `contrato.txt` de cada sessão é a prova de qual versão foi usada, e dá para
  conferir que são iguais com `git diff --no-index` entre os dois;
- a mesma ajuda: as duas com `--exemplo`, ou as duas sem (a tabela marca
  `+exemplo`); e a mesma descrição, ou nenhuma (a tabela marca `+descricao`);
- mais de uma geração por modelo, se der: o resultado de um modelo varia de
  uma execução para outra, e uma execução só não prova que um modelo é
  melhor que o outro.

---

# O modelo dos prompts

O que o agente manda ao modelo em cada fase, o que espera de volta e o que
faz com a resposta. Os textos abaixo são cópias literais do código
(`rvgen/contrato.py` e `rvgen/agente.py`), em inglês como no código;
`{entre chaves}` é o que o agente preenche. Se mudar um prompt no código,
mude aqui também.

---

## 1. A forma de toda conversa

Toda chamada ao modelo tem **duas mensagens**, e só a segunda muda de fase
para fase:

| papel | conteúdo |
|---|---|
| `system` | o **contrato** do tipo de CPU (seção 2) — o mesmo em todas as chamadas de uma geração |
| `user` | o **pedido da fase** (seções 3 a 6) |

Quando a resposta não serve (sem JSON, sem bloco VHDL, entidade com outro
nome), o agente acrescenta a resposta ruim como `assistant` e um novo `user`
pedindo de novo, e tenta **mais uma vez**. As mensagens de nova tentativa
estão na seção 7.

Fluxo das fases (detalhe em `specs/plan.md`, seção 9.1):

```
contrato ─► 1 decomposição (JSON) ─► 2 um arquivo por vez (```vhdl) ─► cpu.toml (sem modelo)
                                                                        │
      ┌──────────────── rvverify: compila? → etapa RV32I → suíte completa
      │                                    │ falhou
      │                 3 qual arquivo? (só se o GHDL não apontou) ─► 4 arquivo corrigido
      │                                                                 │
      └──────────────── mede de novo; se piorou, desfaz ◄───────────────┘
```

| fase | pede | resposta esperada | como é lida | se falhar 2 vezes |
|---|---|---|---|---|
| decomposição | a divisão em blocos | JSON (schema na seção 3) | `extrair_json` + `validar_arquitetura` | usa a decomposição padrão do tipo |
| escrita | um arquivo `src/<bloco>.vhd` | um bloco ```` ```vhdl ```` com `entity <bloco> is` | `extrair_vhdl` | a geração para com erro |
| escolha | qual arquivo tem o bug | JSON `{"file", "reason"}` | `extrair_json` | corrige o `src/cpu_top.vhd` |
| correção | o arquivo inteiro corrigido | um bloco ```` ```vhdl ```` | `extrair_vhdl` | a iteração é gasta, e a próxima leva uma nota |

No Ollama, os pedidos de JSON vão com o schema no campo `format`, o que
**obriga** o modelo a devolver JSON válido. No OpenRouter o schema não é
enviado à API (nem todo modelo roteado aceita `response_format`); vale só o
texto do pedido, e a extração tolera texto em volta do JSON.

### Resposta cortada pelo servidor: uma terceira mensagem

O servidor do Ollama (0.32.1) encerra o streaming, sem `done` e sem erro,
quando o modelo repete o mesmo token por muito tempo. Isso aconteceu de
verdade na primeira execução real: a ULA escrevia
`"00000000000000000000000000000001"`, e cada `0` é um token. Pedir no prompt
para evitar literais longos não resolveu, porque o modelo de 14B ignorou a
regra. Por isso o cliente **retoma** a resposta cortada: reenvia as mesmas
duas mensagens mais uma terceira, com o texto já recebido,

| papel | conteúdo |
|---|---|
| `assistant` | o texto parcial, exatamente como chegou |

e o modelo continua do ponto em que parou (conferido: a emenda sai sem
costura). Isso se repete até 8 vezes por chamada. O número de cortes
aparece no campo `cortes` de cada evento `llm` da sessão.

---

## 2. Prompt de sistema: o contrato

Gerado por `contrato.texto_do_contrato(tipo, isa)`. Tem cerca de 14 mil
caracteres (~3,6 mil tokens) no monociclo RV32IM. O texto exato de cada
geração fica gravado em `<pasta>/.rvgen/sessao-*/contrato.txt`.

````text
You write VHDL for a RISC-V CPU that an automatic conformance suite
(GHDL + cocotb, the `rvverify` validator) will judge by running real RISC-V
programs and comparing the data RAM with a reference model. Follow this
contract exactly: a CPU that deviates from it cannot be observed and fails.

# Target
ISA: RV32I (lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw lbu lhu sb sh sw addi slti sltiu xori ori andi slli srli srai add sub sll slt sltu xor srl sra or and).
{extensao}
Not required: FENCE, ECALL, EBREAK, CSRs, interrupts, misaligned accesses.
Microarchitecture ({tipo}): {microarquitetura}

# Provided files (compiled BEFORE yours; never rewrite, copy or redeclare them)
cpu_package.vhd, memory_package.vhd, mul_div_unit.vhd, data_ram.vhd, data_rom.vhd, data_memory.vhd, instruction_memory.vhd
Use `library ieee; use ieee.std_logic_1164.all; use ieee.numeric_std.all;
use work.cpu_package.all; use work.memory_package.all;` as needed.

# Top level: file src/cpu_top.vhd, exactly this interface
entity cpu_top is
    generic(
        ROM_INIT_FILE  : string  := "";
        ROM_SIZE_WORDS : integer := 0;
        RV32M_ENABLE   : boolean := false
    );
    port(
        rst : in std_logic;   -- asynchronous, ACTIVE HIGH
        clk : in std_logic
    );
end cpu_top;

Inside cpu_top the test bench reads these by hierarchical name, so the labels
and signal names are mandatory:
- instance label `instruction_memory`: entity work.instruction_memory, with
  generic map (ROM_INIT_FILE => ROM_INIT_FILE, ROM_SIZE_WORDS => ROM_SIZE_WORDS);
  asynchronous read of the instruction at `addr`.
- instance label `data_memory`: entity work.data_memory. Pass the full byte
  address (it routes DATA_ROM at 0x00FC8000 and DATA_RAM at 0x00FC8100 by
  itself). Reads are asynchronous, writes happen on the rising edge. Byte and
  halfword loads come back ZERO-extended: the core must sign-extend LB and LH.
- instance label `register_file`: your register file entity, whose storage is
  a signal named `registers` of type `array (0 to 31) of
  std_logic_vector(31 downto 0)` (declare the type in that file).
- signals declared in cpu_top:
{sinais}

Those labels and names are READ by the test bench from outside; use them
exactly as written (`register_file`, not `register_file_inst`). cpu_top itself
must never reach inside another entity: VHDL has no hierarchical names, so
`register_file.registers(...)` or `data_memory.data_ram...` inside cpu_top does
not compile. Connect every block only through its ports: the register file is
written through its own write port.

Reset: while rst = '1' (asynchronous), the PC is RESET_HANDLER_ADDRESS
(0x00000000) and all registers are 0. Programs end in the self-loop
`halt: j halt` (JAL x0, 0); nothing special is needed for it.

# VHDL rules (each one already broke a real design in this project)
1. VHDL-2008 analyzed by `ghdl -a --std=08`. Use only ieee.std_logic_1164 and
   ieee.numeric_std (never std_logic_arith / std_logic_unsigned).
2. Every array the test bench reads is a 1-D array of 32-bit words, never 2-D.
3. Never compute an array index in one signal and its range guard in another
   signal: keep the guard and the indexing in the same conditional expression.
4. Write combinational logic as concurrent assignments; in a combinational
   process assign every output on every path, so no latch is inferred.
5. One entity per file, entity name = file name, English identifiers and
   comments.
6. Start every file with a comment header containing `-- REQ:` and the
   requirement IDs it implements: FR-RV-04 (RV32I semantics), FR-RV-05 (top
   level and memories), FR-RV-06 (observable state), FR-RV-12/FR-RV-13/FR-RV-14
   (M extension), FR-RV-15 (reset), FR-RV-16 (RV32M_ENABLE).
7. When asked for a file, answer with the COMPLETE file in a single ```vhdl
   block: no placeholders, no "...", no other files.

# Provided declarations
{declaracoes_fornecidas}
````

### As partes variáveis do contrato

**`{extensao}`** depende da ISA:

- `rv32im`:
  > RV32M (mul mulh mulhsu mulhu div divu rem remu) when the generic
  > RV32M_ENABLE is true: decode opcode 0110011 with funct7 = 0000001 into
  > ALU_OP_TYPE_MUL .. ALU_OP_TYPE_REMU and instantiate the PROVIDED
  > mul_div_unit inside `if RV32M_ENABLE generate` (it is combinational and
  > already implements division by zero and overflow). When RV32M_ENABLE is
  > false the M instructions need not execute. The test bench runs the same
  > CPU twice: first with RV32M_ENABLE = false, then true.
- `rv32i`:
  > RV32M is NOT required: keep the generic RV32M_ENABLE declared, but you
  > may ignore it and leave mul_div_unit uninstantiated.

**`{microarquitetura}` e `{sinais}`** dependem do tipo (`contrato.TIPOS`). Os
sinais são exatamente os que o `cpu.toml` gerado manda o testbench observar.

| tipo | microarquitetura pedida | sinais obrigatórios no `cpu_top` |
|---|---|---|
| `monociclo` | um ciclo por instrução; busca, decodificação, leitura de registradores, ULA, memória e escrita combinacionais no ciclo; PC, banco e RAM gravam na borda de subida; sem especulação | `pc`, `instr`, `m_dispatch` |
| `multiciclo` | FSM FETCH/DECODE/EXECUTE/MEMORY/WRITEBACK, 3 a 5 ciclos por instrução, registrador de instrução, escrita no banco e na RAM uma vez por instrução; `pc` só muda no último estado | `pc`, `instr` (registrador de instrução), `m_dispatch` |
| `pipeline` | 5 estágios IF/ID/EX/MEM/WB, forwarding MEM→EX e WB→EX, stall de 1 ciclo em load-use, desvios resolvidos em EX com always-not-taken e flush das duas mais novas, escrita no banco visível na leitura do mesmo ciclo | `pc_f`, `instr_f`, `pc_e`, `jump_e`, `stall_pc`, `flush_d`, `flush_f`, `m_dispatch_e` |

**`{declaracoes_fornecidas}`** é montado por `contrato.interfaces_fornecidas()`
lendo os arquivos **reais** de `cpus/rv32i_pipeline/src/`:
`cpu_package.vhd` inteiro, sem comentários (tipos `ALU_OP_TYPE_t`,
`MEM_ACCESS_WIDTH_t`, constantes de opcode e funct); as constantes inteiras
de `memory_package.vhd` (mapa de memória, sem a ROM embutida); e as
declarações `entity ... end` de `instruction_memory`, `data_memory` e
`mul_div_unit`. Se um arquivo fornecido mudar, o prompt muda junto.

---

## 2b. Com `--exemplo`: a CPU de referência no pedido

Com `--exemplo cpus/rv32i_monociclo` (ou outra pasta com `src/*.vhd`), os
pedidos de decomposição e de escrita começam com o VHDL inteiro dessa CPU:

````text
# Reference design (a DIFFERENT verified CPU from this project; adapt its ideas to this contract, do not copy names that the contract fixes differently)
-- {arquivo}.vhd
{conteudo do arquivo}
...
````

Isso soma cerca de 8 mil tokens: suba `RVGEN_NUM_CTX` para `32768`. O uso do
exemplo fica registrado na sessão, para que uma comparação entre modelos
saiba quais gerações tiveram essa ajuda.

## 2c. Com `--descricao`: o pedido do usuário

Com `--descricao` (ou `--descricao-arquivo`), os pedidos de decomposição,
escrita e correção começam com:

````text
# Designer's description of the CPU (free text from the user)
{descricao}
Follow this description wherever it does not conflict with the contract in the system message. Where it conflicts, the contract wins: it is what the validator checks.
````

E o pedido de decomposição ganha uma linha a mais, com o campo `requests`
passando a ser obrigatório no schema:

````text
Also answer `requests`: one entry per item of the designer's description, with the `blocks` that implement it and `how`; if the contract prevents an item, say so in `how` and leave `blocks` empty.
````

`requests` é uma lista de `{"request", "blocks", "how"}` e vai para o
`architecture.json` com a nota `"declared by the model; NOT verified by
rvverify"`.

---

## 3. Decomposição em blocos

````text
Decompose this {tipo} {ISA} CPU into hardware blocks. Answer ONLY with JSON: {"blocks": [{"name", "responsibility", "ports", "satisfies", "design_rationale"}], "notes"}.
Rules: 2 to 8 blocks; each block becomes src/<name>.vhd with `entity <name>`; lowercase names; never reuse a provided entity (cpu_package, data_memory, data_ram, data_rom, instruction_memory, memory_package, mul_div_unit); the LAST block is `cpu_top`, the top level that instantiates the others and the provided memories; `ports` are VHDL port declarations such as "clk : in std_logic"; `satisfies` lists requirement IDs (FR-RV-xx); `design_rationale` justifies the block by area, speed or verifiability. A sound decomposition for this type is: {blocos_padrao}.
````

`{blocos_padrao}` é a lista de nomes da decomposição padrão do tipo: por
exemplo `register_file, alu, decoder, cpu_top` no monociclo.

Schema enviado ao Ollama (`agente.SCHEMA_ARQUITETURA`):

```json
{
  "type": "object",
  "properties": {
    "blocks": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "responsibility": {"type": "string"},
          "ports": {"type": "array", "items": {"type": "string"}},
          "satisfies": {"type": "array", "items": {"type": "string"}},
          "design_rationale": {"type": "string"}
        },
        "required": ["name", "responsibility", "ports", "satisfies", "design_rationale"]
      }
    },
    "notes": {"type": "string"}
  },
  "required": ["blocks"]
}
```

O que o agente confere (`validar_arquitetura`): de 2 a 8 blocos, nomes em
minúsculas e únicos, nenhum nome de entidade fornecida, `cpu_top` presente e
toda `responsibility` preenchida. O **nome do arquivo nunca vem do modelo**:
é sempre `src/<name>.vhd`. O `cpu_top` é movido para o fim (ordem de
análise do GHDL). O resultado vai para `<pasta>/architecture.json`, com
`"origem": "modelo"` ou `"padrao"`.

---

## 4. Escrita de cada arquivo

Um pedido por bloco, na ordem da decomposição (o `cpu_top` por último):

````text
Architecture of this CPU:
- src/{bloco}.vhd: entity {bloco} -- {responsabilidade}
  ports: {porta}; {porta}; ...
(uma linha por bloco)

Entity declarations already written:
-- src/{outro}.vhd
entity {outro} is ... end {outro};
(ou "(none yet)")

Write the complete file src/{bloco}.vhd implementing entity {bloco}.
Responsibility: {responsabilidade}
Ports: {portas, ou "(see contract)"}
````

Só no pedido do `cpu_top` vem uma linha a mais:

````text
This is the TOP LEVEL: follow the 'Top level' section of the contract exactly (generics, ports, instance labels and signal names) and instantiate every other block above.
````

A resposta precisa ter um bloco ```` ```vhdl ```` contendo
`entity {bloco} is`; havendo vários blocos cercados, vale o maior que tiver
`entity`. As "declarações já escritas" são extraídas dos arquivos já
gravados, para cada arquivo novo casar com as portas dos anteriores.

**O `cpu.toml` não passa pelo modelo.** Ele sai de
`contrato.renderizar_cpu_toml`, a partir do contrato do tipo: fontes
fornecidas em ordem de análise, os arquivos gerados, os caminhos de
observação fixados acima e o modo de parada do tipo (`fetch_pc` no
monociclo e no multiciclo, `commit_pc` no pipeline).

---

## 5. A evidência que volta do validador

Depois de cada execução do `rvverify`, o agente monta um texto de evidência
a partir do `--json` (`Agente._evidencia`). São dois formatos:

**Não compilou**: as linhas de erro do GHDL, com o nome do arquivo reduzido:

```text
GHDL compilation failed:
alu.vhd:12:5: no declaration for "foo"
cpu_top.vhd:88:14: port "result" not found
```

Nesse caso **o arquivo a corrigir sai do próprio erro**, e a fase de
escolha é pulada.

**Compilou, mas algum caso falhou**: até 6 casos, cada um com o resumo do
diagnóstico estruturado do `rvverify` (`feedback.resumo_em_texto`, FR-RV-28):

```text
Failing test cases:
- case rv32i/sra [FR-RV-04, FR-RV-22]
    Valor errado na RAM: 64 de 64 resultados divergem
      RAM[0x00fc8104] sra(0xffffffff, 0x00000001): esperado 0xffffffff (-1), obtido 0x7fffffff (2147483647)
      ...
    sugestão: Os 64 resultados de SRA coincidem com SRL. [...]
... and 3 more failing cases
```

Se **todas** as falhas forem "caminho do `cpu.toml` não existe no design",
o arquivo a corrigir é o `src/cpu_top.vhd` direto, porque os nomes
observados vivem lá.

**Checagem estática do contrato**, acrescentada a qualquer evidência
(`contrato.verificar_contrato`). O texto das fontes geradas é conferido
contra o contrato do tipo: os rótulos `instruction_memory`, `data_memory` e
`register_file`, os três generics, os sinais observados, o sinal `registers`
no banco e nenhum `rotulo.sinal` dentro do top. O que divergir entra assim:

```text
Contract check (static inspection of the text; a suggestion):
- src/cpu_top.vhd: cpu_top must instantiate the label `register_file` exactly (found `register_file_inst`; rename it).
- src/cpu_top.vhd: cpu_top uses `register_file_inst.registers`: VHDL has no hierarchical access; connect through ports.
```

Um erro do GHDL continua decidindo o arquivo a corrigir; sem ele, é a
primeira divergência do contrato que decide. A checagem nunca muda o
veredito. Ela foi conferida contra as duas CPUs de referência, com zero
avisos, e contra a CPU que travou na primeira execução real, em que pega os
quatro problemas (três rótulos `*_inst` e o acesso hierárquico). Só quando
nem o GHDL nem a checagem apontam um arquivo, o modelo escolhe (seção 6).

---

## 6. Escolha do arquivo e correção

**Escolha** (só quando nem o GHDL nem o tipo de falha apontam o arquivo):

````text
The CPU was run by the validator.
{evidencia}

Files:
- src/{bloco}.vhd: {responsabilidade}
(uma linha por bloco)

Which ONE file most likely contains the bug? Answer ONLY with JSON {"file": one of [{arquivos}], "reason": "..."}.
````

No Ollama, o schema restringe `file` à lista exata de arquivos (`enum`), de
modo que um modelo local não consegue responder um arquivo inexistente. Se
a resposta não servir, o agente corrige o `src/cpu_top.vhd`.

**Correção**:

````text
The CPU was run by the validator and failed.
{evidencia}

NOTE: {nota}                      <- só quando existe uma nota (abaixo)

Entity declarations of the other files (keep compatible):
{declaracoes dos outros arquivos}

Current content of src/{alvo}.vhd:
```vhdl
{conteudo atual}
```

Fix src/{alvo}.vhd. Keep the entity name and ports unless the evidence shows that the ports themselves are wrong. Answer with the complete corrected file in one ```vhdl block.
````

As duas notas possíveis:

- depois de uma correção que **piorou** o placar (menos casos aprovados, ou
  compilação que deixou de passar) — o arquivo antigo é restaurado e o
  modelo fica sabendo:
  > Your previous change to {alvo} made the result worse ({placar novo}
  > instead of {placar anterior}) and was reverted. Try a different fix.
- depois de uma resposta inutilizável ou **idêntica** ao arquivo atual:
  > Your last answer for {alvo} was unusable or identical to the current
  > file. Make a real change.

**Temperatura mais alta quando o modelo trava.** Só a nota não basta: na
primeira execução real, com temperatura 0,2, o modelo local devolveu o mesmo
arquivo em 10 de 12 correções. Numa segunda execução, com a escada
0,2 → 0,6 → 0,9, ele repetiu o arquivo nas 3 vezes a 0,6 e mudou nas 4 a
0,9. Por isso, a primeira resposta idêntica faz o próximo pedido sair a
**0,9**, e ele **fica** a 0,9 enquanto as alterações não melhorarem o
placar; só uma melhora (compilar, ou mais casos aprovados) volta ao normal
(0,2). A temperatura de cada chamada fica no evento `llm` da sessão.

Cada correção gasta uma iteração do orçamento (`--iteracoes`, padrão 12).
Medir e avançar de etapa (compila → RV32I → completa) não gasta.

---

## 7. Mensagens de nova tentativa

Enviadas como `user`, depois da resposta ruim reenviada como `assistant`:

| fase | mensagem |
|---|---|
| decomposição | `That decomposition is invalid: {motivo}. Send the JSON again.` |
| escrita | ``The answer has no ```vhdl block with `entity {bloco} is`. Send the complete file src/{bloco}.vhd again.`` |
| correção | ``No ```vhdl block with `entity {alvo} is`. Send the complete file.`` |

---

## 8. Onde ver os prompts reais de uma geração

Tudo fica em `<pasta>/.rvgen/sessao-AAAAMMDD-HHMMSS/`:

| arquivo | o que tem |
|---|---|
| `contrato.txt` | o prompt de sistema exato desta geração |
| `sessao.jsonl` | um evento JSON por linha: `inicio`, `llm` (fase, arquivo, provedor, modelo, **mensagens enviadas**, **resposta**, tokens, segundos, cortes, temperatura), `llm_erro`, `rvverify` (etapa, comando, placar, relatório), `reversao`, `correcao_vazia`, `decomposicao_padrao`, `fim` |
| `rvverify/*.json` | o relatório completo de cada execução do validador |
| `resultado.json` | veredito, placar, iterações, chamadas, tokens, tempo, modelo |
| `sim/`, `build/` | logs e biblioteca do GHDL (fora do Git, ver `.gitignore`) |

Nos eventos `llm`, a mensagem de sistema aparece como `@contrato.txt`, para
não repetir 14 mil caracteres a cada chamada.

Para listar, em ordem, as fases e os arquivos pedidos numa sessão:

```bash
python -c "import json,sys; [print(e['fase'], e['alvo'], e['tokens_saida'], e['segundos']) for e in map(json.loads, open(sys.argv[1], encoding='utf-8')) if e['evento']=='llm']" experimentos/ia_mono_qwen14b/.rvgen/<sessao>/sessao.jsonl
```

---

## 9. Como mudar um prompt

| o que mudar | onde |
|---|---|
| o contrato (sistema) | `contrato.texto_do_contrato` |
| microarquitetura, sinais, parada ou blocos padrão de um tipo | `contrato.TIPOS` |
| decomposição | `Agente._planejar` e `SCHEMA_ARQUITETURA` |
| escrita de arquivo | `Agente._escrever_bloco` |
| evidência | `Agente._evidencia` |
| checagem estática do contrato | `contrato.verificar_contrato` |
| temperaturas na repetição | `agente.TEMPERATURAS_NA_REPETICAO` |
| escolha e correção | `Agente._escolher`, `Agente._reescrever` |

Três cuidados:

1. **Nome fixado no contrato é nome lido pelo `cpu.toml`.** Mudar um sinal
   ou label em `TIPOS` sem mudar o `observe`/`halt`/`metrics` do mesmo tipo
   gera uma CPU que o testbench não consegue observar.
2. **Depois de mudar, rode os testes do gerador** (sem GHDL, sem Ollama):
   ```bash
   python -m unittest discover -s rvgen/tests -t .
   ```
3. **Para comparar modelos, não mude o prompt no meio do experimento.** O
   `contrato.txt` de cada sessão é a prova de qual versão foi usada.

---

## 10. Configuração

Pelo `.env` da raiz ou pelo ambiente (o ambiente vence). Tudo opcional.

| variável | padrão | efeito |
|---|---|---|
| `RVGEN_PROVEDOR` | `ollama` | `ollama` (local) ou `openrouter` (externo) |
| `RVGEN_MODELO` | perfil pela VRAM | modelo do Ollama |
| `OLLAMA_HOST` | procura em `127.0.0.1` e `host.docker.internal` | onde está o servidor Ollama |
| `OPENROUTER_API_KEY` | — | chave do provedor externo |
| `SPECHDL_LLM_MODEL` | `openai/gpt-5.6-luna` | modelo externo padrão |
| `RVGEN_NUM_CTX` | `16384` | janela de contexto no Ollama (`32768` com `--exemplo`) |
| `RVGEN_TIMEOUT` | `900` | segundos por chamada ao modelo |
| `RVGEN_EXECUTOR` | `auto` | `local` (GHDL no host) ou `docker` (`spechdl-toolchain`) |
| `RVGEN_IMAGEM_DOCKER` | `spechdl-toolchain` | imagem usada no modo `docker` |

Perfis locais (tamanhos lidos do registro do Ollama em 2026-09-30):

| perfil | modelo | download | quando |
|---|---|---|---|
| `leve` | `qwen2.5-coder:7b` | 4,68 GB | GPU com menos de 10 GB |
| `padrao` | `qwen2.5-coder:14b` | 8,99 GB | GPU de 10 a 23 GB |
| `forte` | `qwen3-coder:30b` | 18,56 GB | GPU de 24 GB ou mais |
