# Plano técnico — SpecHDL

## Stack
- Python 3.11+
- OpenRouter (SDK nativo, `pip install openrouter`) — extração de spec,
  decomposição arquitetural e geração de VHDL (chamadas de LLM); acesso
  unificado a múltiplos modelos por trás de uma única API, modelo escolhido
  via `SPECHDL_LLM_MODEL`, não hardcoded no código
- GHDL — compilação e simulação VHDL
- cocotb — testbench em Python, dirige o DUT VHDL através do GHDL (fluxo
  `make SIM=ghdl`); ambiente de referência é a imagem Docker
  `rafaelcorsi/pl-descomp-cocotb`, a mesma usada no smoke test de
  `examples/toolchain_smoketest/`
- GTKWave — inspeção visual do waveform (`.vcd`) gerado pela simulação,
  usado na triagem manual de falha quando a classificação automática
  (FR-10) não é suficiente
- Yosys + ghdl-yosys-plugin — síntese real para métricas PPA
- Binutils cruzado RISC-V (`riscv64-unknown-elf-as/ld/objcopy/objdump`,
  gerando rv32) — monta os programas de teste de CPU (fase 3b): assembly →
  ELF → binário → `.rm`, mais o disassembly de conferência. Vem dentro da
  imagem Docker do projeto (NFR-05), não de um caminho de toolchain local
- pytest — testes do pipeline Python
- python-dotenv — carrega `.env` (chave do OpenRouter, modelo default) em
  desenvolvimento local
- Streamlit — formulário web local da fase 1 (rubrica interativa: true/false
  + campos técnicos), único ponto de entrada do pipeline (FR-01, NFR-01)
- Typer (ou argparse) — CLI (`spechdl web` abre o formulário; demais
  comandos de reprodutibilidade, ver fase 7)

## Estrutura de pastas proposta

```
specHDL/
├── CLAUDE.md
├── specs/
│   ├── constitution.md
│   ├── spec.md
│   ├── plan.md
│   └── tasks.md
├── templates/
│   └── rubrica.md            # schema/documentação de referência das
│                              # perguntas — o formulário Streamlit
│                              # implementa essas mesmas perguntas (FR-01)
├── src/
│   └── spechdl/
│       ├── ingestion/       # fase 1 — formulário Streamlit + parsing da
│       │                    # rubrica preenchida em EARS
│       ├── architecture/    # fase 2 — decomposição em blocos
│       ├── codegen/         # fase 3 — geração VHDL + testbench
│       ├── software/        # fase 3b — programas de teste de CPU:
│       │                    # geração do assembly, montagem/link
│       │                    # (as/ld/objcopy/objdump), emissão do .rm e
│       │                    # do pacote de ROM
│       ├── verification/    # fase 4 — wrapper do GHDL; fase 4b —
│       │                    # comparação de RAM e cobertura de instruções
│       ├── ppa/             # fase 5 — wrapper do Yosys/ghdl-yosys-plugin
│       ├── report/          # fase 6 — geração do relatório final
│       └── cli.py
├── docker/
│   └── Dockerfile           # imagem do projeto: pl-descomp-cocotb +
│                            # binutils cruzado RISC-V + Yosys (NFR-05)
├── examples/
│   ├── alu_4bit/              # caso de teste fixo, não faz parte do core
│   ├── riscv_base_test/       # FIXTURE GOLDEN, IMUTÁVEL (FR-18):
│   │   ├── src/program.S      # teste obrigatório do RV32I base, escrito
│   │   │                      # direto em assembly
│   │   ├── src/linker.ld
│   │   ├── build/program.dasm # disassembly de conferência (objdump)
│   │   ├── build/program.rm   # código de máquina da ROM
│   │   ├── expected_ram.json  # golden — a IA não edita (princípio 9)
│   │   └── instructions.json  # instruções que este programa deve cobrir
│   ├── RISCV32I/              # CPU RV32I de terceiro (Morgan Demange),
│   │                          # referência de arquitetura; NÃO é gerada
│   │                          # pelo pipeline e não tem teste cocotb
│   └── toolchain_smoketest/   # smoke test do toolchain GHDL+cocotb (T0.2),
│       ├── src/                # não gerado pelo pipeline, fixo
│       └── test/
├── tests/                    # testes pytest do pipeline
└── outputs/                  # artefatos gerados por execução (gitignored)
    ├── <bloco>/
    │   ├── src/<bloco>.vhd
    │   └── test/
    │       ├── test_<bloco>.py
    │       └── Makefile       # segue o padrão cocotb (TOPLEVEL_LANG=vhdl, SIM=ghdl)
    └── software/<programa>/   # fase 3b/4b, um diretório por programa
        ├── program.S
        ├── program.dasm
        ├── program.rm
        ├── rom_image_pkg.vhd  # .rm convertido em pacote VHDL (FR-21)
        ├── expected_ram.json  # gravado ANTES da simulação (FR-22)
        └── test/
            ├── test_program.py
            └── Makefile
```

## Contratos de dados entre fases (JSON simplificado)

**spec.json** (saída da fase 1):
```json
{
  "requirements": [
    {"id": "FR-01", "type": "functional", "text": "...", "source_field": "tem_cache"},
    {"id": "NFR-01", "type": "non_functional", "category": "power|speed|area", "text": "..."}
  ]
}
```
`source_field` aponta pra pergunta/campo da rubrica que originou o requisito
— substitui o antigo `source_excerpt` (que fazia sentido pra texto livre,
não pra uma rubrica estruturada).

**architecture.json** (saída da fase 2):
```json
{
  "blocks": [
    {
      "name": "alu",
      "inputs": ["a", "b", "opcode"],
      "outputs": ["result", "flags"],
      "responsibility": "...",
      "satisfies": ["FR-06", "NFR-02"],
      "design_rationale": "..."
    }
  ],
  "connections": [{"from": "control_unit", "to": "alu", "signal": "opcode"}]
}
```

**block_result.json** (saída das fases 3–5, por bloco):
```json
{
  "block": "alu",
  "vhdl_path": "...",
  "testbench_path": "...",
  "testbench_framework": "cocotb",
  "makefile_path": "...",
  "simulation": {
    "status": "pass|fail",
    "log_path": "...",
    "waveform_path": "...",
    "failed_requirement": null,
    "failure_class": "implementation|spec_gap|null"
  },
  "ppa": {"cells": 0, "estimated_critical_path_ns": 0, "method": "synthesis|heuristic"}
}
```

**spec.json — parte de ISA** (fase 1, só pra design de processador, FR-16):
```json
{
  "isa": {
    "base": "RV32I",
    "extensions": [
      {"name": "M", "kind": "standard", "satisfies": ["FR-04"]},
      {"name": "Xmac", "kind": "custom", "satisfies": ["FR-05"]}
    ],
    "declared_instructions": [
      {"mnemonic": "addi", "source": "RV32I", "satisfies": ["FR-03"]},
      {"mnemonic": "mul",  "source": "M",     "satisfies": ["FR-04"]}
    ]
  }
}
```
Atenção ao namespace: os IDs dentro de `spec.json` e `architecture.json` são
os requisitos **do design gerado** (a CPU do aluno), não os deste documento —
`FR-04` acima é "a CPU tem extensão M", não a NFR-04 do pipeline. Os dois
espaços de numeração coexistem e não se misturam.

`declared_instructions` é o contrato de cobertura: a fase 4b falha se
qualquer mnemônico dessa lista não for aposentado por nenhum programa
(FR-26). Instruções não implementadas (ex.: `fence`, `ecall`, `ebreak` — que
a referência de `examples/RISCV32I/` também não implementa) simplesmente não
entram na lista, e isso fica explícito no relatório em vez de virar uma
falha silenciosa.

**expected_ram.json** (oráculo da fase 3b, consumido pela 4b — FR-22):
```json
{
  "program": "riscv_base_test",
  "authored_by": "golden|generated",
  "word_size_bits": 32,
  "endianness": "little",
  "done_sentinel": {"addr": "0x00FC8FFC", "value": "0xC0FFEE00"},
  "max_cycles": 200000,
  "expected": [
    {"addr": "0x00FC8000", "value": "0x0000000C", "instruction": "addi", "note": "..."}
  ]
}
```
`authored_by: "golden"` marca o arquivo como imutável (princípio 9): o
pipeline recusa gravar em cima dele. Só endereços listados em `expected` são
comparados — o resto da RAM é don't-care, senão qualquer mudança de layout de
stack quebraria o teste por motivo irrelevante. Cada entrada aponta a
instrução que ela evidencia, o que faz a mensagem de falha do FR-24 sair
pronta.

**program_result.json** (saída da fase 4b, um por programa):
```json
{
  "program": "ext_m_test",
  "extension": "M",
  "march": "rv32im",
  "mabi": "ilp32",
  "assembler_version": "riscv64-unknown-elf-as 2.40",
  "artifacts": {"asm": "...", "dasm": "...", "rm": "...", "expected_ram": "..."},
  "simulation": {
    "status": "pass|fail|timeout",
    "cycles_executed": 0,
    "log_path": "...",
    "waveform_path": "...",
    "ram_mismatches": [
      {"addr": "0x...", "expected": "0x...", "got": "0x...", "instruction": "mul"}
    ],
    "failed_requirement": null,
    "failure_class": "implementation|spec_gap|non_termination|null"
  },
  "coverage": {
    "retired_instructions": ["addi", "mul"],
    "declared_not_retired": [],
    "retired_not_declared": []
  }
}
```

## Formato do `.rm` — imagem de código de máquina da ROM

`.rm` é o código de máquina que vai pra ROM de instruções, derivado do ELF
por ferramenta (`objcopy -O binary` → conversor), nunca escrito à mão.

Formato: **texto, uma palavra de 32 bits em hexadecimal por linha**, da
menor pra maior endereço, sem prefixo `0x`, sem aspas e sem vírgula:

```
# program.rm — gerado por spechdl.software.rm (não editar à mão)
# origin=0x00000000  words=97  source=build/program.elf
1100006f
1780006f
fe010113
```

Decisões e por quê:
- **Texto e não binário**: versionável e diffável, atende NFR-03
  (legível por humano e por máquina) e deixa o artefato revisável no PR.
- **Uma palavra por linha, sem sintaxe VHDL**: o mesmo arquivo é consumido
  pelo conversor de ROM e pelo cocotb (que precisa do `.rm` pra decodificar
  o trace de instruções do FR-25). O `.txt` de `examples/RISCV32I/` mistura
  cabeçalho, `x"..."` e vírgulas — serve pra colar em VHDL na mão, não pra
  ser lido por duas ferramentas.
- **Linhas `#` de comentário** carregam origem e proveniência; o parser as
  ignora.
- **Palavra de 32 bits, little-endian na origem**: cada linha já é a
  instrução como a CPU a lê (`1100006f`), não os bytes na ordem da memória —
  a inversão acontece uma vez, no conversor.

**Como o `.rm` entra na ROM (FR-21)**: a fase 3b converte o `.rm` num pacote
VHDL gerado (`rom_image_pkg.vhd`) com o array constante de instruções, e o
Makefile do programa compila esse pacote junto com a CPU. Escolhido em vez de
ler o arquivo com `std.textio` na elaboração porque um ROM com I/O de arquivo
não passa pela síntese do Yosys, e a fase 5 (PPA) precisa sintetizar o mesmo
design que foi verificado. O `.rm` continua sendo o artefato de verdade; o
pacote VHDL é derivado e descartável. Diferença em relação a
`examples/RISCV32I/`: lá o passo de colar o conteúdo em `memory_package.vhd`
é manual, aqui é automático (princípio 6, reprodutibilidade).

## Interface de verificação padrão da CPU (FR-17)

O teste obrigatório é uma fixture golden reaproveitada entre CPUs diferentes,
então ele precisa de um ponto de acoplamento estável. Toda CPU gerada expõe:

| Elemento | Contrato | Para quê |
|---|---|---|
| `clk : in std_logic` | subida ativa | clock do cocotb |
| `rst : in std_logic` | síncrono, ativo em '1' | reset inicial do teste |
| `dbg_pc : out std_logic_vector(31 downto 0)` | PC da instrução aposentada no ciclo | mensagem de falha (FR-28) |
| `dbg_instr : out std_logic_vector(31 downto 0)` | palavra da instrução aposentada | cobertura dinâmica (FR-25) |
| `dbg_valid : out std_logic` | '1' só quando aposenta instrução real | ignora stall e flush |
| RAM de dados | `signal memory` dentro da instância `data_ram_inst`, filha direta do top-level | leitura do estado final pelo cocotb |

Por que trace de **aposentadoria** e não de busca (fetch): num pipeline com
especulação, instrução buscada nem sempre executa. Contar fetch inflaria a
cobertura com instruções descartadas em flush — exatamente o falso positivo
que o princípio 10 proíbe. `dbg_valid` é o que separa os dois.

Por que a RAM precisa ser `signal` e não `variable`: o cocotb lê hierarquia
interna do VHDL via VHPI do GHDL, que expõe sinais, não variáveis de
processo. A `data_ram.vhd` de `examples/RISCV32I/` já usa
`signal memory : DATA_RAM_MEMORY_ARRAY_t`, então o contrato está alinhado com
a referência — mas é uma restrição real de geração de código, não uma
preferência de estilo, e vale registrar por isso.

Alternativa considerada e rejeitada: dump da RAM por porta de debug
dedicada (a CPU exporia um barramento de leitura só pro testbench). Rejeitada
porque adiciona hardware que existe só pro teste, distorcendo as métricas de
área da fase 5. O trio `dbg_*` é barato e pode ser removido na síntese; um
barramento de dump, não.

## Fase 1 em detalhe — formulário Streamlit em vez de texto livre
`templates/rubrica.md` documenta o schema das perguntas (true/false — `Tem
cache?` — e campos técnicos — `Estágios de pipeline: __`, `Largura de
palavra (bits): __` etc.); `spechdl web` sobe um app Streamlit local que
renderiza esse mesmo schema como widgets (checkbox, number_input). O aluno
responde na interface e clica em submeter — nesse momento o app grava
`rubrica.md` preenchido (versionável, NFR-03) e dispara o resto do pipeline
automaticamente, sem pausa humana (NFR-01). A validação de estrutura (FR-03)
roda no próprio formulário antes de liberar o botão de submissão (ex.:
campo `estágios_pipeline` desabilitado se `tem_pipeline` estiver marcado
"não"), não depois. O parser da fase 1 não precisa de LLM pra extrair
sentido de texto ambíguo — é essencialmente determinístico; o que sobra pra
IA é montar o `spec.json` em EARS a partir das respostas já validadas. Não
confundir com os exemplos de referência em `examples/ula32_sol/` e
`examples/ula32_terra/` — esses foram gerados contra o modelo antigo (texto
livre) por um agente externo, servem só como prova de que o método SDD
funciona ponta a ponta, não como formato de fixture pra fase 1.

## Fase 3/4 em detalhe — testbench via cocotb
Cada bloco gerado vem com um testbench cocotb (Python) e um `Makefile` no
padrão `TOPLEVEL_LANG = vhdl`, `SIM = ghdl`, `MODULE = test_<bloco>`,
`VHDL_SOURCES = ../src/<bloco>.vhd` — o mesmo padrão usado em
`examples/toolchain_smoketest/`. O wrapper Python da fase 4 (T4.1) roda
`make -C outputs/<bloco>/test/` e captura exit code + log, em vez de chamar
`ghdl` diretamente; quem invoca o GHDL por baixo é o próprio cocotb. Ambiente
de referência (usado também na CI de smoke test): imagem Docker
`rafaelcorsi/pl-descomp-cocotb`.

Quando a simulação falha (FR-10), a triagem decide entre duas rotas: bug de
implementação — regenerar o bloco na própria fase 3 — ou lacuna de
spec/arquitetura — voltar pra fase 1 (spec incompleta) ou fase 2 (decomposição
errada), ver `constitution.md` princípio 5. O waveform (`.vcd`) fica salvo em
`waveform_path` no `block_result.json` pra inspeção manual no GTKWave quando a
classificação automática não é suficiente pra decidir a rota.

Para CPU, isso é o piso e não o teto: bloco por bloco verificado não prova
que o processador executa programas (princípio 8). O design só fecha depois
da fase 4b, abaixo.

## Fase 3b/4b em detalhe — verificação de CPU rodando software

Só se aplica quando o design alvo é um processador. Fluxo, por programa:

```
program.S ──as──> program.o ──ld──> program.elf ──objdump──> program.dasm
                                          │
                                          └──objcopy -O binary──> program.bin
                                                                       │
                                                                   conversor
                                                                       ▼
                            rom_image_pkg.vhd <──gerador──────── program.rm
                                    │
                                    ▼
  expected_ram.json (gravado ANTES) ──> cocotb + GHDL ──> program_result.json
```

**Um Makefile por programa**, no mesmo padrão do resto do projeto, mas com a
CPU inteira mais o pacote de ROM na lista de fontes:

```make
TOPLEVEL_LANG = vhdl
TOPLEVEL      = cpu
VHDL_SOURCES  = ../rom_image_pkg.vhd $(wildcard ../../../src/*.vhd)
MODULE        = test_program
SIM           = ghdl
SIM_ARGS     += --vcd=program.vcd
```

**O testbench cocotb** (`test_program.py`) faz sempre a mesma coisa, e é por
isso que ele pode ser uma fixture reaproveitada: solta o reset, e a cada
borda de clock em que `dbg_valid = '1'` decodifica `dbg_instr` em mnemônico
(em Python, direto da palavra de 32 bits) e acumula o conjunto de instruções
aposentadas; para quando o sentinela de término aparece no endereço combinado
ou quando estoura `max_cycles`; então lê `data_ram_inst.memory` e compara com
`expected_ram.json`, endereço por endereço.

**Por que assembly escrito à mão em vez de C compilado.** O teste é escrito
direto em assembly pela IA. A razão é o FR-26: a cobertura tem que ser
instrução por instrução, e com C quem decide o que é emitido é o compilador —
ele não gera `auipc` ou `sltiu` só porque existem na ISA, pode trocar uma
instrução por outra equivalente entre versões, e com otimização ligada apaga
o teste inteiro por constant-folding. Fechar cobertura assim exigiria encher
o C de `__asm__ volatile`, o que é assembly com passos extras. Escrevendo
`.S` direto, o conjunto de instruções emitidas é exatamente o que a IA
escreveu — determinístico e auditável linha por linha contra o
`instructions.json`.

O que se perde: o C exercitaria de graça o caminho real de codegen
(prólogo/epílogo de função, uso de stack, convenção de chamada, `.rodata`),
que é justamente onde CPU gerada costuma quebrar. Então isso passa a ser
responsabilidade explícita do programa em assembly, e não um efeito colateral
do compilador — o teste obrigatório **precisa** incluir, escrito à mão:
chamada e retorno (`jal`/`jalr`), salvamento e restauração de registradores
em stack, e leitura de constante do `.rodata` via `auipc`/`lui` + offset.

Regras do programa de teste, em qualquer caso:
1. Cada instrução escreve seu resultado num endereço distinto e conhecido da
   RAM — é isso que transforma "a instrução executou" em "a instrução
   executou *corretamente*", e é o que liga cada linha de `expected` ao seu
   mnemônico.
2. Operandos vêm de registradores já carregados em runtime, não de valores
   que o montador possa resolver — pseudo-instrução que expande pra outra
   coisa (`li`, `mv`, `nop`, `j`) conta como a instrução real expandida, e é
   isso que o `program.dasm` serve pra conferir.
3. O programa termina escrevendo o sentinela no endereço combinado e entrando
   em loop infinito — sem isso o testbench não sabe distinguir "acabou" de
   "travou" (FR-28).

**Cobertura é união, falha é individual**: a cobertura do FR-26 é avaliada
sobre a união de todos os programas (o obrigatório cobre o RV32I base, cada
teste de extensão cobre a sua). Já pass/fail de RAM é por programa — um teste
de extensão que falha não contamina o resultado do base, e o relatório
mostra os dois separados.

**Ordem de execução e gate**: o teste obrigatório roda primeiro. Se ele
falhar, a CPU está quebrada no básico e testar extensão em cima disso só
produz ruído — a fase 5 não roda e o relatório declara a CPU não verificada
(FR-29).

**Triagem de falha** reaproveita a lógica do FR-11, com uma classe a mais:
`non_termination` (o programa nunca sinalizou fim, FR-28), que quase sempre
aponta para desvio/branch ou hazard mal implementado, não para a instrução
sob teste.

## Toolchain de CPU — imagem única, sem instalação manual (NFR-05)

`docker/Dockerfile` estende `rafaelcorsi/pl-descomp-cocotb` (que já traz
GHDL + cocotb, e é a imagem usada na CI do smoke test) adicionando o
binutils cruzado RISC-V (`as`, `ld`, `objcopy`, `objdump` — via o pacote
`binutils-riscv64-unknown-elf` do bookworm; não entra compilador C, porque
os programas de teste são escritos direto em assembly) e o Yosys da fase 5.
Alvo rv32 via flags (`-march=rv32i…`, `-mabi=ilp32`), não via toolchain
separado. A imagem base é pinada por digest e as versões dos pacotes por
`ARG`, pra que o build não mude de resultado com o tempo (princípio 6). O
`ghdl-yosys-plugin` não é pacote Debian e não entra no T0.6: é o T0.3 que
decide entre buildar o plugin ou cair no fallback heurístico do FR-14.

Build e uso:

```bash
docker build -t spechdl-toolchain -f docker/Dockerfile docker
docker run --rm -v "${PWD}:/job" spechdl-toolchain make -C examples/toolchain_smoketest/test/
```

Por que imagem própria em vez de documentar `apt install`: o `Makefile` de
`examples/RISCV32I/compilation/` aponta pra
`./xpack-riscv-none-elf-gcc-14.2.0-1/bin/…`, um diretório que não está no
repositório — ou seja, aquele exemplo **não monta** num clone limpo. Isso é
exatamente a violação do princípio 6 (reprodutibilidade) que a NFR-05 existe
pra fechar. Com a imagem, `docker run` no repo clonado monta e simula sem
mais nada instalado — inclusive no Windows, que é o ambiente de
desenvolvimento real aqui (não há GHDL nem binutils cruzado no PATH da
máquina; Docker e WSL2, sim).

O `-march` de cada programa é derivado das extensões declaradas em
`spec.json` (`RV32I` + `M` → `rv32im`), não fixado no código — princípio 7.

## Fase 5 em detalhe — por que síntese real em vez de a IA "chutar" PPA
Yosys, com o plugin ghdl-yosys-plugin, lê VHDL usando o GHDL como frontend,
sintetiza para uma biblioteca de células genérica e roda o comando `stat`
para contagem de células/área. Isso dá números de verdade em vez de uma
estimativa da LLM — muito mais defensável numa apresentação acadêmica. Se o
setup do plugin não for viável dentro do prazo da disciplina, cair para o
fallback heurístico do FR-13, deixando isso explícito no relatório final.

## Acesso a LLM — por que OpenRouter
Decisão do professor da disciplina: todas as chamadas de LLM do pipeline
(extração EARS na fase 1, decomposição na fase 2, geração de VHDL na fase 3)
passam pelo SDK nativo do OpenRouter (`pip install openrouter`), não pelo
Anthropic SDK direto — substituição total, não convivência dos dois. O
OpenRouter dá acesso a vários provedores/modelos por trás de uma única API
com uma única chave (`OPENROUTER_API_KEY`), o que facilita controle de custo
e de acesso pra turma inteira. O modelo usado não fica fixo no código: é lido
de `SPECHDL_LLM_MODEL` (variável de ambiente), seguindo o princípio 7 da
constitution (ferramenta genérica, não hardcoded). Default atual (em
`.env.example`): `openai/gpt-5.6-luna`, um modelo rápido/econômico — se uma
fase específica (ex.: decomposição arquitetural) precisar de mais raciocínio,
trocar o valor da variável é suficiente, sem alterar código. T0.4 valida a
chave e faz uma chamada mínima antes de qualquer uso real nas fases
seguintes; `scripts/llm_playground.py` é o utilitário solto pra isso — não é
código de pipeline, é só validação manual de conectividade.

## Fase gate
Não iniciar a fase N+1 até que todas as tarefas da fase N em `tasks.md`
estejam marcadas como concluídas e o critério de aceite verificado — ver
`constitution.md`, princípio 1. Isso inclui aprovação humana explícita: os
testes automatizados passando não bastam pra avançar de fase — pare ao final
de cada fase e aguarde confirmação do usuário antes de iniciar a tarefa
seguinte.

Nota: este gate é sobre o processo de **desenvolver** o SpecHDL (fase por
fase de `tasks.md`) — não sobre a **execução** do pipeline já pronto, que
roda sem pausas humanas depois que o aluno submete a rubrica (NFR-01). São
dois conceitos de "fase" com o mesmo nome por coincidência (o backlog de
desenvolvimento espelha as fases do próprio pipeline), não confundir os
dois.
