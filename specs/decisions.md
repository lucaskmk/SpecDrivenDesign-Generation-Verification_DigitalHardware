# Decisões e premissas — Trilha RISC-V

Registro das decisões de arquitetura e compatibilidade da trilha RISC-V
(Emenda 1 da `constitution.md`). Formato ADR enxuto: contexto → decisão →
consequência. Nenhuma decisão aqui foi tomada por inferência: todas as
afirmações sobre o comportamento do design vieram de execução real de
ferramenta, registrada em `ADR-000`.

---

## ADR-000 — Auditoria do repositório (linha de base factual)

**Contexto.** O objetivo da trilha é evoluir uma CPU RISC-V existente. Antes
de qualquer alteração era necessário estabelecer o que existe de fato, em vez
de presumir interfaces.

**Método.** Leitura dos 19 arquivos VHDL de `examples/RISCV32I/src/` mais
execução real de GHDL 4.1.0 e cocotb 2.1.0 em WSL Ubuntu 24.04.

**Achados (todos verificados por execução):**

| Item | Achado |
|---|---|
| CPU | `src/CPU.vhd` — implementada, não apenas prevista. Autoria de Morgan Demange (`simple_RISCV_RV32I_vhdl`), vendorizada no commit `f884a4e` |
| Top-level | `entity CPU` tem **apenas** as portas `rst` e `clk`. Nenhuma saída observável |
| Pipeline | 5 estágios: fetch, decode, execute, memory, write-back. Harvard |
| Reset | `rst` **ativo em nível alto**, assíncrono (`program_counter.vhd:41`, `register_file.vhd:58`) |
| Clock | único domínio `clk`. O banco de registradores escreve na **borda de descida** (`register_file.vhd:60`), decisão original para reduzir hazards |
| ROM de instruções | `instruction_memory.vhd` — **assíncrona/combinacional, latência 0 ciclo**. Sem porta de clock |
| Conteúdo da ROM | constante VHDL `INSTRUCTION_MEMORY_CONTENT` em `memory_package.vhd` (97 palavras / 388 bytes). **Não existe leitura de arquivo** |
| ROM de dados | `data_rom.vhd` — assíncrona, 8 bytes, base `0x00FC8000` |
| RAM de dados | `data_ram.vhd` — leitura **assíncrona (latência 0)**, escrita síncrona em `rising_edge(clk)`, 512 bytes, base `0x00FC8100` |
| Mapa de memória | instruções `0x00000000`+; DATA_ROM `0x00FC8000`; DATA_RAM `0x00FC8100` (confirmado em `linker.ld`) |
| Acesso a instruções | `pc_f` → `instruction_memory.addr`; instrução disponível no mesmo ciclo |
| Acesso a dados | `alu_result_m` → `data_memory`, wrapper que roteia RAM vs ROM por comparação de endereço (`data_memory.vhd:64`) |
| Hazards | forwarding MEM→EX e WB→EX; stall de 1 ciclo em load-use; flush em branch/jump tomado. Preditor: always-not-taken |
| Subconjunto RV32I | RV32I base completo **exceto** `FENCE`, `ECALL`, `EBREAK`, que o decoder marca como inválidas. Sem CSR, sem interrupções. `invalid_instr` é instanciado como `open` em `CPU.vhd:168`, ou seja, detectado e descartado |
| Ferramentas WSL | GHDL 4.1.0 (mcode), Yosys 0.33, make, gtkwave, gcc |
| Compilador RISC-V | **ausente** no Windows e na WSL |
| `ghdl-yosys-plugin` | **ausente** |

**Execuções reais realizadas nesta auditoria:**

1. `ghdl -a --std=08` nos 19 arquivos RTL → **exit 0**, sem erros.
2. `ghdl -e --std=08 CPU` → **exit 0**.
3. `ghdl -a` em `CPU_tb.vhd` → **falha**. Os literais `5ns`, `12ns`, `1ms`
   estão sem espaço, o que é ilegal em VHDL; falha até com `-frelaxed`. **O
   testbench VHDL existente nunca rodou em GHDL.**
4. cocotb + GHDL sobre a `entity CPU`, 50 ciclos após reset: a CPU **executa
   de verdade** o programa que está na ROM. `pc_f` avança até `0x154`, `sp` e
   `gp` inicializados, `x28 = 0x0b` (o valor `11` da variável `var` de
   `compilation/main.c`).
5. `ghdl synth --std=08 --out=verilog CPU` → **exit 0**, 40.888 linhas.
6. `yosys -p 'read_verilog; hierarchy -top CPU; stat'` → **exit 0**.
   Baseline medida: **6.937 células**, 22.302 wires, 3.104 bits de memória.

**Consequência.** A CPU é um ponto de partida válido e funcional. Os
problemas reais não estão na CPU, mas na **observabilidade** e na **carga de
programa** — tratados em ADR-002 e ADR-003.

---

## ADR-001 — Trabalhar no design existente com generic `RV32M_ENABLE`

**Contexto.** É preciso comparar RV32I contra RV32IM. Havia três caminhos:
alterar `examples/RISCV32I` no lugar, duplicar a árvore em
`examples/RISCV32IM`, ou parametrizar.

**Decisão.** Trabalhar em `examples/RISCV32I/src/` e introduzir um generic
`RV32M_ENABLE : boolean`. Com `false`, o comportamento é o do design original;
com `true`, a extensão M é habilitada.

**Motivo.** Duplicar 19 arquivos VHDL faria qualquer correção ter de ser
aplicada em dois lugares e deixaria as duas árvores divergirem. O generic dá
um A/B honesto sobre a **mesma** base de código: a diferença medida é a
extensão M, e não ruído de duas cópias.

**Consequência.** Nada é removido (`constitution.md`, princípio 8). A baseline
é obtida elaborando o mesmo design com `RV32M_ENABLE=false`, atendendo
FR-RV-16 e NFR-RV-03. Exige que a lógica de multiplicação/divisão seja
condicionada por `generate`, para que a configuração desabilitada não pague
custo de área.

---

## ADR-002 — Refatorar `data_ram` de array 2D para array 1D de palavras

**Contexto.** FR-RV-06 exige verificar resultados na RAM pelo cocotb.
`DATA_RAM_MEMORY_ARRAY_t` é declarado como
`array (0 to N, 3 downto 0) of std_logic_vector(7 downto 0)` — um array **2D**.
Verificado por execução: o VPI do GHDL **não expõe arrays 2D**, e
`dut.data_memory.data_ram.memory` resulta em `AttributeError`. Em contraste,
`register_file.registers` (array 1D de `std_logic_vector`) e
`instruction_memory.memory` (idem) **são lidos sem problema**.

**Decisão.** Alterar o tipo da RAM de dados para
`array (0 to N-1) of std_logic_vector(31 downto 0)`, implementando os acessos
de byte e halfword por slicing do vetor de 32 bits.

**Alternativas rejeitadas.**
- *Porta de debug no RTL*: adiciona portas que existem só para teste, e
  ainda assim exigiria varredura endereço a endereço.
- *Verificar apenas por registradores*: não cumpre o critério de aceitação de
  verificar resultados na RAM.

**Consequência.** É uma alteração em bloco de terceiro, portanto FR-RV-07
exige comprovar que o comportamento foi preservado — inclusive as regras
originais de acesso desalinhado (retornar `0xFFFFFFFF` na leitura e descartar
a escrita). A mesma refatoração se aplica a `data_rom.vhd`, que usa o mesmo
padrão 2D.

---

## ADR-003 — ROM com carga por arquivo `.ram` via generic, mantendo a constante

**Contexto.** FR-RV-08/09 exigem imagens `.ram` trocáveis por caso de teste.
Dois achados restringem as opções:

1. **Não existe formato `.ram` neste repositório.** A ROM não lê arquivo
   nenhum: o programa é uma constante VHDL. O fluxo atual, documentado em
   `examples/RISCV32I/README.md`, é manual — `make`, depois
   `convert_bin_to_txt.py`, depois **copiar e colar** o resultado dentro de
   `memory_package.vhd`.
2. **O cocotb não consegue escrever na ROM.** Verificado por execução:
   `dut.instruction_memory.memory[0].value = ...` é **silenciosamente
   ignorado** pelo VPI do GHDL. Carregar a imagem em runtime pelo Python está
   descartado.

**Decisão.** Adicionar à `instruction_memory` um generic
`ROM_INIT_FILE : string := ""`:

- vazio (padrão) → usa `INSTRUCTION_MEMORY_CONTENT`, preservando o
  comportamento atual e a sintetizabilidade (FR-RV-10);
- preenchido → lê a imagem `.ram` por `textio` na elaboração.

**Formato `.ram` definido** (documentado porque não havia formato a descobrir
— este é o formato que passa a existir):

- uma palavra de 32 bits por linha;
- 8 dígitos **hexadecimais**, sem prefixo `0x`, case-insensitive;
- a linha de índice 0 corresponde ao endereço de byte `0x00000000`, e a linha
  `n` ao endereço `4*n` — ou seja, ordem crescente de endereço;
- o valor hexadecimal é a **instrução como palavra de 32 bits** (o mesmo
  valor que a constante VHDL usa). O little-endian do design está na
  organização de bytes da memória, não na grafia do arquivo;
- linhas vazias e linhas iniciadas por `#` são comentário;
- palavras não informadas são preenchidas com `0x00000000`;
- **convenção de parada:** o programa termina em auto-laço (`JAL x0, 0`,
  encoding `0x0000006f`), que é o que o `startup.S` original já faz no rótulo
  `spin`. O testbench detecta término por PC estacionário, não por instrução
  mágica fora da ISA (FR-RV-03).

**Consequência.** Nenhuma edição manual de VHDL para trocar de programa. O
caminho de síntese continua usando a constante. Risco a validar durante a
implementação: `ghdl synth` pode não aceitar a função de leitura de arquivo
mesmo quando o generic está vazio — se isso ocorrer, isolar a leitura por
`generate`.

---

## ADR-004 — Montador RV32IM próprio, em Python, no lugar do GCC RISC-V

**Contexto.** FR-RV-18/19 pedem benchmarks `.c` e programas `.asm`. Verificado
por execução: **não existe compilador RISC-V** no Windows nem na WSL
(`riscv64-unknown-elf-gcc`, `riscv-none-elf-gcc`, `riscv32-unknown-elf-gcc`,
`clang`, `llvm-mc` — todos ausentes). O `Makefile` em
`examples/RISCV32I/compilation/` aponta para um toolchain xPack em caminho
Windows (`./xpack-riscv-none-elf-gcc-14.2.0-1/bin/...exe`) que não está no
repositório. FR-RV-20 e a instrução explícita do escopo proíbem instalar
ferramentas silenciosamente.

**Decisão.** Escrever um montador RV32I/RV32IM determinístico em Python,
versionado no repositório, que traduz `.asm` → `.ram`. Os arquivos `.c`
permanecem versionados como **especificação legível do algoritmo** de cada
benchmark, com rótulo explícito de que **não foram compilados neste
ambiente**.

**Motivo.** Mantém o fluxo autocontido e reprodutível sem alterar a máquina
do usuário, e o montador é ele próprio testável por pytest — o que um binário
externo não seria. Como o gerador de imagens passa a ser código do projeto,
ele entra na cadeia de rastreabilidade.

**Consequência.** O montador é código novo e portanto suspeito: um bug nele
apareceria como falha de hardware. Mitigação obrigatória: testes de
codificação instrução a instrução, conferidos contra os encodings da
especificação RISCV não privilegiada, **antes** de ser usado para gerar
imagens de teste da CPU. Nenhuma métrica ou resultado será atribuído à CPU sem
o montador estar validado.

**Pendência registrada.** Se `gcc-riscv64-unknown-elf` for instalado depois, o
fluxo `.c` real passa a ser possível como caminho alternativo, e os `.c`
deixam de ser apenas documentação. Não é bloqueante para a trilha.

---

## ADR-005 — Síntese real via `ghdl synth --out=verilog` + Yosys

**Contexto.** FR-RV-25 pede área por síntese real. O `ghdl-yosys-plugin`
**não está instalado** e compilá-lo exigiria sudo e dependências de build.

**Decisão.** Usar o backend de síntese do próprio GHDL para emitir Verilog e
alimentar o Yosys com esse Verilog:

```
ghdl synth --std=08 --out=verilog CPU > cpu_synth.v
yosys -p 'read_verilog cpu_synth.v; hierarchy -top CPU; stat'
```

**Motivo.** Verificado por execução: ambos os passos retornam **exit 0** e o
`stat` produz contagem real de células. Dispensa o plugin e não requer sudo.

**Consequência.** As métricas de área são **medição real** de síntese, não
heurística — FR-RV-25 é atendido sem cair no fallback. Ressalva a declarar no
relatório: `stat` sobre células genéricas do Yosys mede complexidade
estrutural relativa, adequada para comparar RV32I contra RV32IM no mesmo
fluxo, e **não** equivale a área em µm² de um PDK nem a LUTs de um FPGA
específico. Caminho crítico não sai do `stat`; só será reportado se uma
execução real de ferramenta o fornecer.

---

## ADR-006 — Contornos de ambiente aplicados

**Contexto.** Dois problemas de ambiente atrapalhavam a execução.

**Decisões.**

1. **`/mnt/c` da WSL estava quebrado** (mount 9p retornando
   `Input/output error`, impedindo a WSL de ler o repositório). Resolvido com
   `wsl --shutdown` e reinício da distro, **com autorização do usuário**.
   Verificado depois: `/mnt/c` acessível.
2. **cocotb não estava instalado e não havia `pip`.** Instalado
   `cocotb 2.1.0` em um virtualenv de usuário (`~/venv-cocotb`), criado com
   `python3 -m venv`. **Sem sudo e sem alterar pacotes do sistema.**

**Consequência.** O ambiente de execução é a WSL Ubuntu 24.04 local, não a
imagem Docker `rafaelcorsi/pl-descomp-cocotb` citada em `plan.md` (o daemon do
Docker está desligado nesta máquina). Os comandos de reprodução no relatório
final devem indicar o venv explicitamente. A imagem Docker continua sendo o
ambiente de referência do projeto para CI.

---

## ADR-007 — Unidade RV32M combinacional, selecionada pelo enum `ALU_OP_TYPE_t`

**Contexto.** A extensão M precisa entrar num pipeline de 5 estágios de
terceiro que já funciona e já está verificado (43 testes verdes). Duas
perguntas de projeto: *qual latência* a unidade tem, e *como* o sinal de
seleção viaja de Decode até Execute.

**Decisão 1 — latência de 1 ciclo, unidade puramente combinacional.**
`mul_div_unit.vhd` calcula MUL/MULH/MULHSU/MULHU e DIV/DIVU/REM/REMU em lógica
combinacional, no mesmo ciclo em que a instrução está em EX, exatamente como a
ALU ao lado dela. O divisor é restaurador: 32 estágios de comparação e
subtração encadeados.

**Decisão 2 — o seletor viaja pelo `alu_op_type`, que já existe.**
As oito operações M foram *acrescentadas ao enum* `ALU_OP_TYPE_t`
(`cpu_package.vhd`), em vez de virarem um sinal de controle novo.

**Motivo.** As duas decisões juntas fazem a extensão custar **zero alteração**
na parte mais delicada do design:

| Bloco | Alteração exigida |
|---|---|
| `fetch_pipeline_register.vhd` | nenhuma |
| `decode_pipeline_register.vhd` | nenhuma |
| `execute_pipeline_register.vhd` | nenhuma |
| `mem_pipeline_register.vhd` | nenhuma |
| `hazard_control_unit.vhd` | nenhuma |
| `ALU.vhd` | nenhuma (o `others` final já cobre os valores novos) |

`alu_op_type` já é propagado de D para E pelo `decode_pipeline_register`, e o
resultado da unidade M é multiplexado sobre `alu_result_e` — que é justamente
de onde partem os caminhos de forwarding MEM→EX e WB→EX existentes. Logo
forwarding, stall de load-use e flush continuam valendo para instruções M sem
uma linha de código nova. Como a latência é de 1 ciclo, **não existe nova fonte
de stall a tratar** (FR-RV-17).

As únicas alterações de decodificação são `control_unit.vhd` (emite os oito
tipos novos quando `funct7 = 0000001`, guardado por `RV32M_ENABLE`) e
`instruction_decoder.vhd` (deixa de marcar esse `funct7` como instrução
inválida).

**Alternativa rejeitada — unidade iterativa multiciclo.** É o que um projeto
real faria para não estourar o caminho crítico. Foi rejeitada nesta primeira
versão porque exigiria acrescentar uma porta `stall` ao
`decode_pipeline_register` (que hoje só tem `flush`), para segurar o estágio EX
enquanto a unidade itera, e reescrever a precedência stall/flush/carga na
`hazard_control_unit`. Isso é mudança estrutural num pipeline de terceiro já
verificado, com risco alto de regressão — e o pedido era pela solução **mais
simples**. Fica registrada como trabalho futuro, com o custo já levantado.

**Consequência — o custo é real, foi medido, e não é pequeno.**
Medição por síntese real (ADR-009), a mesma árvore de fontes, mudando só o
generic:

| Métrica (medida) | RV32I | RV32IM | Δ |
|---|---:|---:|---:|
| Células do núcleo (sem memórias) | 6.239 | 56.327 | **+50.088 (9,03×)** |
| Células totais (com memórias) | 100.284 | 150.372 | +50.088 (1,50×) |
| Células só da `mul_div_unit` | — | 49.824 | — |
| Profundidade lógica da ALU (níveis) | 36 | 36 | 0 |
| Profundidade lógica da `mul_div_unit` (níveis) | — | **631** | — |

Leitura honesta: a extensão M **não economiza um único ciclo por instrução**
neste design — ela reduz a *contagem de instruções* do programa, trocando
rotinas de emulação por uma instrução única, mas o preço é um bloco
combinacional 17,5× mais profundo que a ALU. Numa síntese com restrição de
tempo real, esse caminho ditaria o período de clock do processador inteiro. É
exatamente o argumento a favor da variante multiciclo, e é o resultado que dá
substância à comparação pedida.

**Observabilidade.** `CPU.vhd` expõe `m_dispatch_e` (`'1'` quando uma instrução
M **real** — não uma bolha de flush — está em EX). O harness conta esse sinal
para reportar "instruções RV32M executadas" (FR-RV-24). O sinal existe nas duas
configurações, valendo 0 constante na baseline, para que a mesma métrica seja
coletada dos dois lados sem caminho condicional.

---

## ADR-008 — Término detectado no commit (EX), não no PC de busca

**Contexto.** O harness declarava término contando visitas de `pc_f` (o PC de
busca) ao endereço do auto-laço de parada. Verificado por execução: **isso está
errado e produzia resultado incorreto com hardware correto.**

A CPU é *always-not-taken* e resolve saltos só em EX. Num laço terminado por
`j loop`, o `pc_f` visita especulativamente os dois endereços seguintes ao
salto antes de o salto ser resolvido — e um deles é o endereço do auto-laço de
parada. Ou seja, `pc_f` passa pelo endereço de parada **uma vez por iteração do
laço**. O teste `test_sum_loop` (soma 1..10 = 55) parava na 4ª iteração e
obtinha 6.

**Decisão.** Detectar término no **commit**, não na busca: o programa terminou
quando a instrução de salto que está *no* endereço de parada chega ao estágio
EX e é tomada, o que é exatamente `pc_e == halt_pc and jump_e = '1'`. O flush
do `decode_pipeline_register` zera `jump_out`, então uma bolha nunca satisfaz
essa condição — a detecção é imune ao fetch especulativo.

Depois da detecção, o harness roda `HALT_DRAIN_CYCLES = 5` ciclos extras para
que uma escrita em RAM ainda em MEM/WB se complete. Esses ciclos são contados
em `drain_cycles`, **fora** da métrica de ciclos.

**Consequência.** A contagem de ciclos passa a ter definição precisa e
defensável: *ciclos do fim do reset até o auto-laço de parada executar em EX*.
Sem isso, nenhuma comparação de eficiência RV32I × RV32IM teria significado,
porque o ponto de parada seria arbitrário. Esta ADR **substitui** a frase do
ADR-003 que dizia "o testbench detecta término por PC estacionário": o PC nunca
fica estacionário nesta CPU, justamente porque o salto é resolvido em EX.

**Correção associada — contagem de instruções.** A fórmula era
`fetches - flush_d`, que desconta duas vezes os ciclos de stall de load-use:
`flush_d` é assertado tanto por stall quanto por salto tomado, mas o stall não
mata instrução nenhuma — ela é apenas re-emitida no ciclo seguinte, porque
`stall_f` segura o registrador de fetch. A fórmula correta, agora documentada
no próprio código, é:

    instruções = fetches - flush_f - (flush_d - stalls)

---

## ADR-009 — Como a área é contada: hierarquia preservada e `techmap`

**Contexto.** A receita ingênua do ADR-005
(`read_verilog; hierarchy -top CPU; stat`) dá números enganosos, por dois
motivos descobertos por execução:

1. **Achatar zera o design.** A `entity CPU` não tem porta de saída nenhuma
   (ADR-000). Com `synth -top CPU -flatten`, o Yosys conclui corretamente que
   nada é observável e elimina o circuito inteiro: **0 células**.
2. **Sem `techmap`, os operadores não são expandidos.** Um `stat` logo após
   `hierarchy` conta o multiplicador e o divisor como poucas células genéricas,
   fazendo a extensão M parecer custar ~219 células — subestimando o custo real
   em mais de duas ordens de grandeza.

**Decisão.** O fluxo de medição, implementado em
`examples/RISCV32I/tools/synth_ppa.py`, é:

    ghdl synth --std=08 -gRV32M_ENABLE=<false|true> --out=verilog CPU > cpu_<cfg>.v
    yosys -p 'read_verilog cpu_<cfg>.v; hierarchy -top CPU; proc; memory -nomap;
              opt_expr; techmap; opt_expr; stat'

- **Hierarquia preservada** (sem `flatten`): cada submódulo é otimizado contra
  as suas próprias portas, que são reais, então nada é eliminado indevidamente.
  A área total é a soma dos submódulos — todos instanciados uma vez neste
  design.
- **`techmap` aplicado**: os operadores viram lógica de portas, que é o que
  torna a comparação significativa.
- **Dois totais reportados**: com e sem os blocos de armazenamento
  (`data_ram`, `data_rom`, `instruction_memory`, `register_file`). A RAM de
  dados de 512 bytes vira sozinha ~93 mil células de flip-flop e domina o
  total; como as memórias são idênticas nas duas configurações, o número que
  informa a decisão de arquitetura é o do **núcleo**. Nenhum dos dois é
  escondido.

**O que o número significa e o que não significa.** São células genéricas do
Yosys (`$_AND_`, `$_MUX_`, `$_NOT_`, `$_OR_`, `$_XOR_`, `$_DFF_*_`). Servem
para comparar RV32I contra RV32IM no mesmo fluxo — que é o que a trilha pede —
e **não** equivalem a área em µm² de um PDK nem a LUTs de um FPGA específico.
`ltp -noff` dá o caminho topológico mais longo em **níveis de lógica**: é
medição estrutural real do Yosys, não atraso em nanossegundos. Onde o relatório
fala em tempo de execução, diz explicitamente que é ESTIMATIVA (ciclos ×
período nominal de 10 ns), porque o período realmente atingível não foi medido.

**Nota histórica.** As 6.937 células registradas no ADR-000 são do RTL
**original** (`f884a4e`), antes da refatoração de memórias do ADR-002 e com a
receita antiga. Não são comparáveis com os números acima e não devem ser usadas
como alvo; a referência válida é a coluna RV32I desta mesma árvore, remedida
pelo mesmo script que mede a coluna RV32IM.
