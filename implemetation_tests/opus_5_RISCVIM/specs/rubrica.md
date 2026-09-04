# Rubrica preenchida

> Fase 1 do pipeline (FR-01, FR-02). Formato espelha
> `render_markdown()` de `src/spechdl/ingestion/web_form.py` (uma linha por
> campo do schema de `src/spechdl/ingestion/schema.py`).
>
> Duas ressalvas de proveniência, registradas aqui em vez de escondidas:
>
> 1. A seção **ISA RISC-V** (base + extensões) é exigida pelo FR-16, mas o
>    schema do formulário ainda não a renderiza — é a tarefa T1.5, pendente
>    em `specs/tasks.md`. Nesta execução a seção foi preenchida seguindo
>    diretamente o contrato do FR-16 / `plan.md` (bloco `isa` do
>    `spec.json`), sem alterar o código do formulário.
> 2. Dois campos do schema não conseguem expressar este design; ver
>    `SPEC-GAP-01` e `SPEC-GAP-02` em `spec.md`. As respostas abaixo são as
>    honestas, não as que fariam a validação cruzada ficar verde.

## Modelo geral da máquina

- **Largura da palavra (bits)**: 32
- **Largura do endereço (bits)**: 32
- **Harvard (memórias de instrução e dados separadas)?**: True
- **Load/store puro (RISC)?**: True
- **Endereçamento por byte?**: True
- **Little-endian?**: True
- **Exige acessos alinhados?**: True
- **Número de registradores de propósito geral**: 32
- **Largura do registrador (bits)**: 32
- **Registrador zero fixo (R0 sempre 0)?**: True
- **Banco de registradores separado para FP?**: False

## ISA e formato de instrução

- **Largura da instrução (bits)**: 32
- **Tamanho fixo de instrução?**: True
- **Quantos formatos de instrução (tipo R/I/J)**: 6
- **Bits de opcode**: 7
- **Quantidade de instruções no conjunto**: 45
- **Usa campo funct (extensão de opcode)?**: True
- **Bits de imediato**: 12
- **Imediato com extensão de sinal?**: True
- **Três operandos (rd, rs, rt)?**: True
- **Número de modos de endereçamento**: 2
- **Base + deslocamento?**: True
- **Indexado (reg + reg)?**: False
- **PC-relativo nos desvios?**: True
- **Auto-incremento/decremento?**: False
- **Push/pop dedicados?**: False
- **Tem registrador de flags (Z, N, C, V)?**: False
- **Desvios condicionais usam flags?**: False
- **Tem delay slot de branch?**: False
- **Tem instrução de chamada com link (jal)?**: True
- **Multiplicação em hardware?**: True
- **Divisão em hardware?**: True
- **Barrel shifter (shift em 1 ciclo)?**: True
- **Ponto flutuante?**: False
- **SIMD/vetorial?**: False
- **Instruções atômicas (LL/SC ou CAS)?**: False
- **syscall/trap dedicado?**: False
- **NOP explícito na ISA?**: False

## ISA RISC-V (FR-16 — seção pendente no formulário, ver T1.5)

- **ISA base**: RV32I
- **Extensões padrão selecionadas**: M
- **Extensões custom**: (nenhuma)
- **Zicsr / CSRs**: False
- **fence / ecall / ebreak implementados?**: False

## Microarquitetura (datapath + controle)

- **Número de estágios de pipeline (1 = monociclo)**: 1
- **Multiciclo microprogramado?**: False
- **CPI alvo**: 1.0
- **Frequência de clock alvo (MHz)**: 50
- **Forwarding/bypass?**: False
- **Detecção de hazard com stall em hardware?**: False
- **Predição de desvio?**: False
- **Penalidade de desvio errado (ciclos)**: 0
- **Superescalar?**: False
- **Execução fora de ordem?**: False
- **SMT?**: False
- **Número de cores**: 1
- **Cores homogêneos?**: True
- **Portas de leitura do banco de registradores**: 2
- **Portas de escrita do banco de registradores**: 1
- **Número de ALUs / unidades funcionais**: 2

## Hierarquia de memória

- **Níveis de cache**: 0
- **Tamanho do bloco/linha (bytes)**: 4
- **Write-back?**: False
- **Write-allocate no miss de escrita?**: False
- **Política de substituição**: 0
- **Penalidade de miss (ciclos)**: 1
- **Coerência entre cores?**: False
- **Memória virtual/MMU?**: False
- **Largura do barramento de memória (bits)**: 32
- **Capacidade de RAM (MB)**: 1
- **Canais/bancos de memória**: 1
- **Boot ROM?**: True
  - **Tamanho (KB)**: 4
- **Scratchpad local (sem cache)?**: True

## E/S, barramento e interrupções

- **E/S mapeada em memória?**: True
- **Número de periféricos**: 0
- **Tem interrupções?**: False
- **DMA?**: False
- **Número de barramentos**: 1
- **Número de masters no barramento**: 1
- **Precisa de árbitro?**: False
- **Timer?**: False
- **UART?**: False
- **GPIO?**: False
- **Watchdog?**: False

## Proteção e exceções

- **Modos de privilégio (kernel/usuário)?**: False
- **Proteção de memória (MPU ou MMU)?**: False
- **Exceções precisas?**: False
- **Número de causas de exceção suportadas**: 0

## Implementação física (PPA)

- **Alvo é FPGA?**: True
- **Orçamento de área (LUTs ou células)**: 10000
- **Orçamento de potência (mW)**: 500
- **BRAMs/DSPs disponíveis**: 10
- **Domínios de clock**: 1
- **Reset síncrono?**: True
- **Reset ativo em nível baixo?**: False
- **Interface de debug (JTAG)?**: False

## Software / ABI

- **Vai ter assembler próprio?**: False
- **Compilador C?**: False
- **SO/RTOS?**: False
- **Registradores de argumento**: 8
- **Registradores salvos pelo callee**: 12
- **Tamanho padrão da pilha (KB)**: 1
- **Pilha cresce pra baixo?**: True
