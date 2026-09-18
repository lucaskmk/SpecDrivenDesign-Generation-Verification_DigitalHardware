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

**Revisão (2026-09-18, TRV-7.7.7).** A premissa "não existe toolchain RISC-V
neste ambiente" deixou de valer: `docker/Dockerfile` (NFR-RV-05) traz
`binutils-riscv64-unknown-elf` 2.40 e Yosys 0.23 numa imagem de container, sem
instalar nada na máquina do usuário. Isso **não** revoga a decisão acima. O
montador Python continua sendo o caminho principal, por três motivos que a
imagem não muda: é autocontido (roda sem Docker), é testável por pytest
instrução a instrução, e faz parte da cadeia de rastreabilidade do projeto. O
binutils real entra no papel que a *Consequência* acima pedia — o de mitigar o
risco de um bug no montador aparecer como falha de hardware —, como **oráculo
de cross-check**: `rvverify/tests/test_assembler_oracle.py` monta os mesmos
fontes pelos dois caminhos e compara palavra a palavra (490 palavras na
primeira execução, todas coincidentes). Conforme NFR-RV-05, a ausência da
imagem pula essa conferência e nunca reprova a suíte. A **Pendência
registrada** acima segue aberta: a imagem tem só `binutils`, não tem compilador
C, então o fluxo `.c` real continua indisponível e os `.c` continuam sendo
documentação do algoritmo.

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

---

## ADR-010 — Interface web com `http.server` e Server-Sent Events, não Streamlit

> **REVERTIDA pela ADR-012** (2026-09-18): o professor definiu que o trabalho é
> de terminal e não pede interface gráfica. O registro fica porque o problema
> que ele descreve — uma execução de um minuto que despeja 1.576 linhas de log
> — continua valendo, e foi resolvido pelo relatório de terminal de FR-RV-30 e
> pelo log por caso da ADR-011. Nenhuma linha de servidor web foi escrita.

**Contexto.** A validação de uma CPU leva cerca de um minuto (26 casos, cerca
de 2,4 s cada, medido na monociclo em 2026-09-17), e a síntese das duas
configurações leva mais 68 s. Pela linha de comando isso aparece como 1.576
linhas de log, das quais 805 são avisos `metavalue detected` do GHDL. O
usuário pediu uma interface para enviar a CPU, escolher testes e ver o que
passa e o que falha **enquanto** roda (FR-RV-30).

**Verificado no ambiente (ADR-006).** O venv `~/venv-cocotb` (Python 3.12.3)
não tem FastAPI, Flask, Starlette, uvicorn, Streamlit nem `python-multipart`.
O módulo `cgi` ainda existe, mas está obsoleto desde o 3.11 e foi removido no
3.13.

**Decisão.** Servidor com `http.server.ThreadingHTTPServer` da biblioteca
padrão, página única com HTML, CSS e JavaScript próprios, e resultados
empurrados ao navegador por **Server-Sent Events** (`EventSource`). O envio de
arquivos é JSON com o conteúdo em base64, e o `.zip` é aberto com `zipfile`.
Assim nada depende de `cgi` nem de multipart.

**Alternativas rejeitadas.**
- *Streamlit* — já está no stack da trilha A, mas não está instalado neste
  venv. Além disso, o modelo de reexecutar o script a cada interação torna
  desajeitados o acompanhamento contínuo, o cancelamento e a retomada depois
  de recarregar a página. Seria uma dependência nova para um resultado pior.
- *FastAPI + WebSocket* — duas dependências novas para um fluxo que é de mão
  única (servidor → navegador). SSE cobre esse fluxo com reconexão automática.
- *Página estática que lê um JSON gravado no fim* — não mostra nada em tempo
  real, que é o pedido.

**Consequência.** Nenhuma instalação nova (NFR-RV-04). A interface funciona
offline e só em `127.0.0.1`. O custo é escrever à mão o roteamento e a
validação de entrada, o que é cercado por testes em
`rvverify/tests/test_web.py`.

---

## ADR-011 — Validação em subprocesso, com eventos JSON Lines e log do GHDL por caso

**Contexto.** A interface precisa de três coisas que a linha de comando não
dava: saber quando cada caso começa e termina, cancelar uma execução e
mostrar o log de um caso sem misturá-lo com o dos outros.

**Decisão.**
1. O servidor roda `python -m rvverify <cpu> --eventos --workdir <dir>` como
   **subprocesso**, em um grupo de processos próprio. Cancelar é enviar
   `SIGTERM` ao grupo (e `SIGKILL` 3 s depois, se preciso), o que leva junto
   os `ghdl` filhos. Uma thread Python não pode ser interrompida no meio de um
   `subprocess.run`, então rodar a validação dentro do servidor não permitiria
   cancelar.
2. `--eventos` imprime uma linha `@rvverify <json>` por evento (plano,
   compilação, início e fim de item, etapa pulada, relatório, fim). O prefixo
   separa evento de log sem exigir um segundo descritor de arquivo.
3. `rvverify.builder.run_simulation` e `build_design` aceitam `log_file`, que
   o `cocotb_tools.runner` já suporta. A suíte de conformidade grava a saída
   do GHDL de cada caso em `<caso>/sim.log`. A saída principal fica só com o
   progresso legível, o que também resolve o excesso de log da linha de
   comando. As suítes pytest existentes não passam `log_file` e se comportam
   como antes.
4. O testbench genérico passa a gravar `report.json` **também quando o caso
   falha**, com as divergências estruturadas (`falhas`) e o erro (`erro`), e é
   daí que sai o diagnóstico de FR-RV-28, em vez de interpretar a mensagem de
   exceção.

**Alternativas rejeitadas.**
- *Validação em thread dentro do servidor* — sem cancelamento (item 1), e um
  `sys.exit` do runner do cocotb derrubaria o servidor.
- *Extrair resultados do log do GHDL com expressões regulares* — frágil, e é
  exatamente o tipo de inferência que NFR-RV-02 proíbe quando existe um
  relatório estruturado.

**Consequência.** A linha de comando ganha `--eventos`, `--workdir`,
`--casos`, `--listar`, `--eficiencia` e `--area`. A interface é só um cliente
dela, e qualquer coisa que a interface mostra também sai por
`python -m rvverify --json`.

---

## ADR-012 — Sem interface gráfica: o validador é de terminal

**Contexto.** A ADR-010 projetou uma interface web local para acompanhar a
validação. Antes de qualquer linha de servidor ser escrita, o professor
definiu a direção do trabalho: **continuar no terminal, interface não é
necessária**. O que o trabalho precisa ter são os testes, e testes rigorosos.

**Decisão.** O validador é operado por linha de comando e só por ela
(NFR-RV-04). O que a interface resolveria vira exigência da saída de terminal:

| dor que a interface atacava | como o terminal resolve |
|---|---|
| 1.576 linhas de log por execução | saída do GHDL vai para o `sim.log` de cada caso (ADR-011); a tela recebe uma linha por caso |
| não saber o que está acontecendo | progresso impresso no instante em que cada caso termina, com tempo e ciclos |
| não saber o que corrigir | diagnóstico estruturado de FR-RV-28, com entrada, esperado, obtido e a instrução que a CPU parece estar executando |
| escolher o que rodar | `--casos` e `--etapa`, e o comando pronto que repete só o que falhou |
| acompanhar de fora | `--eventos` (JSON Lines), para CI e para avaliar modelos de IA em lote |

**Consequência.** O esforço que iria para servidor, HTML e JavaScript vai para
o **rigor da suíte** (FR-RV-34 e FR-RV-35), que é o que mede de fato se um
aluno ou um modelo de IA construiu a CPU. Nada de web foi implementado, então
não há código a remover: só a spec e o backlog mudaram.

---

## ADR-013 — Estrutura do repositório: validador no centro, trilha A no legado

**Contexto.** O repositório cresceu em duas trilhas e a pasta `examples/`
misturava coisas de naturezas diferentes: a CPU RISC-V de referência
(`examples/RISCV32I/`), uma segunda CPU (`examples/rv32i_monociclo/`), dois
exercícios de ULA da trilha A (`examples/ula32_sol`, `examples/ula32_terra`) e
um smoke test de toolchain. Na raiz conviviam `src/spechdl/`, `templates/`,
`.streamlit/`, `abrir_formulario.bat`, `outputs/` e os documentos das duas
trilhas. Quem chega não descobre por onde começar, e o nome `RISCV32I` em caixa
alta não diz que aquela é a CPU a ser modificada.

**Decisão.** Cinco pastas na raiz, cada uma com uma função só:

| pasta | o que é | antes |
|---|---|---|
| `rvverify/` | o validador: manifesto, montador, modelo de referência, harness, suíte e diagnóstico | `rvverify/` + `examples/RISCV32I/tools/rv_assembler.py` + `examples/RISCV32I/test/reference_model.py` |
| `cpus/rv32i_pipeline/` | a CPU de referência de 5 estágios — o ponto de partida do aluno | `examples/RISCV32I/` |
| `cpus/rv32i_monociclo/` | a CPU monociclo, prova de que a suíte julga comportamento e não formato | `examples/rv32i_monociclo/` |
| `entregas/` | onde a CPU entregue entra, com `_modelo/` para copiar | `entregas/` com `_template/` |
| `legado/` | a trilha A inteira, preservada e fora do caminho | `src/spechdl/`, `templates/`, `tests/`, `scripts/`, `.streamlit/`, `abrir_formulario.bat`, `examples/ula32_*`, `examples/toolchain_smoketest` |

Duas mudanças de dependência vêm junto:

1. **O montador e o modelo de referência sobem para `rvverify/`** (`asm.py` e
   `reference.py`). Eles são infraestrutura do validador, não da CPU de
   exemplo: o validador montava programas a partir de uma pasta chamada
   `examples/`, o que inverte a direção da dependência e quebraria se aquele
   exemplo saísse. As suítes da CPU de referência passam a importá-los do
   pacote.
2. **`pyproject.toml` passa a servir a trilha B**: `pythonpath = ["."]` e
   `testpaths = ["rvverify/tests", "cpus"]`. Antes apontava para `src/` e
   `tests/` (trilha A), e por isso toda execução de pytest da trilha B exigia
   `-o addopts=` na linha de comando.

**Alternativas rejeitadas.** Repositório separado para a trilha A (quebra o
princípio 8 e o histórico); manter `examples/` com tudo dentro (o problema);
apagar os exercícios de ULA (princípio 8).

**Consequência.** `git log --follow` continua seguindo cada arquivo. Todo
caminho citado em spec, plano, tarefas, decisões, README e manifestos foi
atualizado no mesmo commit da mudança, e a suíte inteira roda depois dela para
provar que nada ficou apontando para o lugar antigo.

---

## ADR-014 — Conclusão da ADR-013 e adoção do oráculo Docker do montador

**Contexto.** A ADR-013 decidiu cinco pastas de topo, mas o commit `2091e0d`
executou só metade dela: renomeou `examples/RISCV32I/` → `cpus/rv32i_pipeline/`
e `examples/rv32i_monociclo/` → `cpus/rv32i_monociclo/`, sem criar `legado/` e
sem promover o montador e o modelo de referência para `rvverify/`. A
*Consequência* registrada na ADR-013 — "todo caminho citado em spec, plano,
tarefas, decisões, README e manifestos foi atualizado no mesmo commit da
mudança, e a suíte inteira roda depois dela" — **não se cumpriu**. Três
caminhos ficaram para trás em código Python executável, e as três suítes
reprovavam na `main`:

| arquivo | sintoma |
|---|---|
| `rvverify/tests/test_manifest.py` | apontava para `examples/RISCV32I/cpu.toml`; 5 testes reprovando |
| `cpus/rv32i_monociclo/test/test_monociclo.py` | `sys.path` derivado de `EXAMPLES/RISCV32I`; módulo inteiro falhava na coleta |
| `cpus/rv32i_pipeline/test/rv_build.py` | montava o prefixo do `git show` a partir do caminho de HOJE, então a extração do RTL original (commit `f884a4e`, onde o design estava em `examples/RISCV32I/`) voltava vazia e o A/B de FR-RV-07 reprovava |

Em paralelo, um plano de merge antigo e nunca executado
(`hey-claude-please-plan-jolly-bird.md`) continha uma peça que ainda valia: uma
imagem Docker com `binutils` RISC-V cruzado real, útil como oráculo do montador
Python da ADR-004. O `Dockerfile` daquele branch citava `NFR-05`/`T0.6`, IDs que
não existem nesta `main`.

**Decisão.**

1. **Concluir a ADR-013 como decidida**, em commits pequenos e verificados
   (`TRV-7.7.0` a `TRV-7.7.12`): criar `legado/` e mover para lá a trilha A
   inteira; esvaziar `examples/`, que deixa de existir; promover
   `rv_assembler.py` → `rvverify/asm.py` e `reference_model.py` →
   `rvverify/reference.py`; reapontar todo importador, documento, comentário
   de VHDL e comando de copiar-colar. Tudo por `git mv`.
2. **Restaurar as suítes antes de qualquer outra coisa** (`TRV-7.7.0`). Um
   gate de "suíte verde" não significa nada partindo de uma suíte vermelha. Em
   `rv_build.py`, o prefixo histórico virou a constante `ORIGINAL_PREFIX`,
   justamente para não voltar a acompanhar reorganizações da árvore.
3. **Manter `testpaths` do `pyproject.toml` sem `legado/`.** Não há um único
   teste na trilha A (`docs/ESTADO-TRILHA-A.md`), então incluí-la só daria a
   impressão de cobertura onde não há nenhuma.
4. **Trazer o oráculo Docker formalizado como `NFR-RV-05` antes do código**
   (`TRV-7.7.5` antes de `TRV-7.7.6`/`TRV-7.7.7`), em vez de copiar o
   `Dockerfile` citando um requisito inexistente. A ADR-004 ganhou um bloco
   *Revisão*: o binutils real é cross-check, não substituto.
5. **Arquivar, não apagar, o plano de merge antigo**, com nota no topo
   separando o que foi aproveitado do que foi superado.
6. **Publicar `REPO_MAP.md`** na raiz, com o lembrete de mantê-lo atualizado.

**Alternativas rejeitadas.**

- *Mover `cpus/` de volta para dentro de `examples/`* — foi o pedido inicial
  do usuário, checado contra a ADR-013 e revertido: aquela pasta misturava
  exercícios da trilha A com as CPUs de referência, e `RISCV32I` em caixa alta
  não sinalizava que era o alvo editável do aluno. A ADR-013 já havia decidido
  isso, com justificativa registrada.
- *Adotar o binutils real como montador principal* — quebraria a
  autocontenção que a ADR-004 buscava: o montador Python roda sem Docker e é
  testável por pytest instrução a instrução, o que um binário externo não é.
- *Corrigir os três caminhos quebrados junto com os commits de conteúdo* —
  misturaria "restaurar o que estava quebrado" com "mudar de lugar", e a
  bissecção deixaria de distinguir as duas coisas.
- *Reescrever os documentos históricos* (`docs/MUDANCAS.md`,
  `mudancas-riscv.html`, `RELATORIO.md`) para refletir a estrutura nova —
  rejeitado pelo princípio 8. Corrigiram-se links quebrados e comandos de
  copiar-colar; a prosa histórica ficou, com nota. A única exceção,
  deliberada, está registrada no commit do `TRV-7.7.8`: uma nota do HTML
  afirmava que o `pyproject.toml` apontava o pytest para a trilha A, o que a
  ADR-013 tornou falso, e deixar instrução errada ao lado de um comando para
  copiar seria pior do que corrigi-la.

**Consequência.** `examples/` não existe mais e `git ls-files examples/`
devolve vazio. `git log --follow` segue cada arquivo movido, inclusive o plano
arquivado. A direção de dependência ficou certa: `rvverify` não importa nada de
`cpus/`. Diferente da ADR-013, esta decisão foi verificada por execução real, e
não por leitura: `pytest rvverify/tests`, `pytest cpus/rv32i_pipeline/test` e
`pytest cpus/rv32i_monociclo/test` rodaram com GHDL 2.0.0 e cocotb 2.0.0 (imagem
`rafaelcorsi/pl-descomp-cocotb`) e terminaram em exit code 0; `docker build` da
imagem nova e a conferência dos três executáveis também. O oráculo comparou 490
palavras sem divergência, e que ele não passa a vazio foi provado por mutação
(`SRA` codificado como `SRL` reprova a suíte). Fica pendente, por não ser
verificável localmente: o workflow `toolchain-smoketest.yml` teve os caminhos
reapontados para `legado/`, mas só um push real ou `workflow_dispatch` confirma
que os filtros de `on.push.paths` disparam.

## ADR-015 — Imagem Docker do Quartus para RV-8, separada para sempre da imagem do oráculo

**Contexto.** O professor pediu uma etapa nova, depois da suíte de
conformidade da RV-7: rodar o Quartus Prime Lite sobre a CPU validada e medir
viabilidade de FPGA de verdade — cabe (`Fitter`), frequência/timing
(`TimeQuest`) e potência estimada (`Power Analyzer`), alvo inicial Cyclone V
`5CEBA4F23C7N`. O plano detalhado está em
`docker/quartus-docker-fpga-analysis-plan.md`; esta ADR registra as decisões
de infraestrutura que aquele plano não fixa sozinho, e que vieram de execução
real, não de leitura de documentação:

1. **A imagem tem que ficar separada para sempre da imagem do oráculo**
   (`docker/Dockerfile`, NFR-RV-05), por pedido explícito e por engenharia:
   o oráculo é ~200 MB (binutils + Yosys sobre a imagem de referência da
   disciplina) e roda em **todo** `pytest rvverify/tests`; o Quartus Prime
   Lite sozinho passa de 2 GB e só é relevante para quem pediu a análise de
   FPGA. Misturar as duas obrigaria toda execução do oráculo a puxar
   gigabytes de ferramenta de FPGA que não usa.
2. **A URL de download hardcoded no rascunho anterior deste Dockerfile
   estava morta.** `curl -I` contra
   `https://downloads.intel.com/akdlm/software/acdsinst/25.1std/1129/ib_installers/QuartusLiteSetup-25.1std.0.1129-linux.run`
   devolve HTTP 301 para
   `corpredirect.intel.com/Redirector/404Redirector.aspx?404;...` — a árvore
   `akdlm` nesse host está fora do ar, e o mesmo aconteceu testando uma
   versão mais antiga (24.1std/1077) no mesmo host. O host vivo é
   `download.altera.com` (não `downloads.intel.com`): o mesmo caminho
   `akdlm/software/acdsinst/25.1std/1129/ib_installers/cyclonev-25.1std.0.1129.qdz`
   devolveu `Content-Disposition: attachment; filename="cyclonev-25.1std.0.1129.qdz"`
   de um `AkamaiGHost` de verdade — prova de que o nome de arquivo e a versão
   `25.1std.0.1129` já presentes no rascunho **estão certos**, só o host
   estava errado. Isso é coerente com a Altera ter voltado a ser empresa
   independente da Intel: o download voltou para infraestrutura `altera.com`.
3. **O CDN da Altera bloqueia download automatizado, e isso não tem
   contorno por script.** Toda tentativa contra `download.altera.com`
   (instalador e `.qdz`, versões 24.1std e 25.1std, com e sem User-Agent e
   Referer de navegador) devolveu HTTP 403 do `AkamaiGHost`. A página de
   download (`www.altera.com/downloads/...`) também devolve 403 pro mesmo
   `curl`. Isso é mitigação de bot **e** um aceite de licença que a Altera
   deliberadamente prende a uma sessão de navegador — não uma URL errada.
   Como isso vale igual dentro de um `RUN curl` do `docker build`, não só
   numa tentativa isolada, **o Dockerfile parou de tentar baixar
   automaticamente**.
4. **Os checksums sha1 hardcoded no rascunho anterior não podiam ser
   confirmados e foram tratados como não confiáveis.** Sem conseguir
   completar um download de verdade (item 3), não havia como produzir nem
   conferir um hash real; um checksum que não pode ser verificado é pior do
   que nenhum, porque finge uma garantia de integridade que não existe.

**Decisão.**

1. `docker/Quartus_Dockerfile` passa a **copiar** o instalador e os `.qdz`
   de `docker/quartus_installers/` (pasta local, fora do Git — ver o
   `README.md` daquela pasta) em vez de baixar com `curl`. O usuário baixa os
   arquivos uma vez, manualmente, aceitando a licença no navegador — é
   exatamente o passo que a Altera já exige de qualquer humano, então não é
   uma etapa extra imposta por este projeto, só reconhece a que já existia.
2. O `base_url` errado (`downloads.intel.com`) é substituído por
   `download.altera.com` nos comentários e na documentação — não no código
   do Dockerfile, que não builda mais nenhuma URL, exatamente para não
   reintroduzir uma tentativa de download automático que sabe-se que falha.
3. Os checksums sha1 fixos foram removidos. O Dockerfile imprime o sha256 de
   cada arquivo que efetivamente usou (log de reprodutibilidade) e confere
   contra um `SHA256SUMS` opcional se o usuário criar um, mas nunca trava o
   build por um hash que este projeto não pode provar que é o correto.
4. Formalizado como `NFR-RV-06` (`specs/spec.md`): as duas imagens nunca
   compartilham `FROM`, nunca viram um único Dockerfile, e a execução default
   de `rvverify` nunca depende da imagem do Quartus estar presente.
5. A arquitetura da nova etapa (RV-8) entra em `specs/plan.md`, seção 8, e o
   backlog em `specs/tasks.md`, Fase RV-8 — todas as tarefas de
   implementação do wrapper ficam com o checkbox **em aberto**: nada foi
   executado de verdade ainda (nem pode, sem os arquivos de
   `docker/quartus_installers/`), e a Fase RV-7 (a suíte que roda **antes**
   desta etapa) ainda não fechou (`TRV-7.2` a `TRV-7.6` em aberto) — o gate
   de fase do `plan.md`, seção 6, aplica-se aqui: RV-8 é especificada agora,
   implementada só com aprovação explícita do usuário.

**Alternativas rejeitadas.**

- *Tentar automatizar o aceite de licença/contornar a mitigação de bot da
  Akamai* (por exemplo, navegador headless simulando o clique de "Accept")
  — rejeitado: é contornar de propósito um controle de consentimento que o
  fornecedor colocou ali deliberadamente, não um bug a se desviar.
- *Manter os checksums sha1 antigos "por garantia"* — rejeitado: um hash
  inventado passa a falsa impressão de que a integridade do binário foi
  conferida, o que é pior do que declarar explicitamente que não foi.
- *Unificar `docker/Dockerfile` e `docker/Quartus_Dockerfile` numa imagem só,
  com um estágio opcional de Quartus* — rejeitado pelo pedido explícito do
  usuário e pela desproporção de tamanho (item 1 do Contexto); um multi-stage
  build ainda obrigaria a etapa cara a existir na mesma árvore de build do
  oráculo leve.
- *Escrever já o wrapper Python/Tcl do fluxo Quartus (síntese, fit, timing,
  potência) nesta mesma mudança* — rejeitado por hoje: nenhuma execução real
  contra o Quartus é possível sem a imagem construída, que depende do
  download manual (item 1 da Decisão) e do fechamento da Fase RV-7; escrever
  o wrapper antes disso violaria o princípio 1 (nada de simulação declarada
  sem rodar de verdade) por não ter como testá-lo.

**Consequência.** `docker/Quartus_Dockerfile` builda de forma determinística
a partir de arquivos locais, sem tentar (e falhar) uma rede bloqueada; a
mensagem de erro quando falta um arquivo aponta exatamente pro passo manual
que falta, em vez de um erro genérico de instalador. `docker build` da
imagem em si **não foi executado** nesta ADR — falta o download manual dos
~2 GB de instalador, que só o usuário pode completar (item 3 do Contexto) —
então "a imagem builda de verdade" continua em aberto em `specs/tasks.md`
até essa execução real acontecer. Nenhum número de PPA de FPGA existe ainda;
nenhum é declarado.
