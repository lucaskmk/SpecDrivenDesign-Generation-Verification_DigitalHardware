# O que mudou — trilha RISC-V, RV32I → RV32IM

Diff explicado do que a trilha RISC-V fez no repositório. Ponto de partida:
commit `f884a4e` ("RISCV32I example"), que vendorizou a CPU. Ponto de chegada:
`1185a7e`.

Complementa o [`RELATORIO.md`](../examples/RISCV32I/RELATORIO.md), que responde
"o que foi medido"; este arquivo responde **"o que foi mexido e o que não foi"**.

> Versão visual, com o diagrama do datapath antes/depois:
> [`mudancas-riscv.html`](mudancas-riscv.html).

---

## 1. Regra que governou todas as mudanças

> **Nada é removido. Evoluir por parametrização, não por deleção nem
> duplicação.** — `specs/constitution.md`, Emenda 1, princípio 8.

Consequência prática: **todo generic novo tem default igual ao comportamento
original.** Elaborar a CPU sem passar parâmetro nenhum produz exatamente o
RV32I de `f884a4e`.

```vhdl
entity CPU is
    generic(
        ROM_INIT_FILE   : string  := "";     -- "" -> constante VHDL original
        ROM_SIZE_WORDS  : integer := 0;      -- 0  -> tamanho original
        RV32M_ENABLE    : boolean := false   -- false -> RV32I original
    );
    port( rst : in std_logic;  clk : in std_logic );
end CPU;
```

Isso não é promessa: `test_memory.py::TestBehaviourPreservation` extrai o RTL
antigo do git com `git show f884a4e:...`, elabora as duas árvores sob o **mesmo**
testbench e compara PC final e os 32 registradores.

---

## 2. O que NÃO foi tocado

### Trilha A (o app SpecHDL) — byte a byte idêntica

```
git diff --stat f884a4e HEAD -- src/ tests/ templates/ .streamlit/
→ (vazio)
```

`src/spechdl/`, `tests/`, `templates/rubrica.md`, `.streamlit/config.toml`,
`abrir_formulario.bat`, `pipeline_sdd_hardware.png` — nenhum commit.

### Dentro da CPU — os blocos mais delicados

```
git diff --quiet f884a4e HEAD -- \
    src/fetch_pipeline_register.vhd  src/decode_pipeline_register.vhd \
    src/execute_pipeline_register.vhd src/mem_pipeline_register.vhd \
    src/hazard_control_unit.vhd
→ exit 0        (byte a byte iguais)
```

Também intactos: `ALU.vhd`, `branching_unit.vhd`, `register_file.vhd`,
`program_counter.vhd`, `extend_32.vhd`, `data_memory.vhd`.

**11 dos 19 arquivos VHDL originais não mudaram uma linha.** Isso não é sorte —
é o resultado direto da decisão de projeto explicada na seção 4.

---

## 3. As três mudanças, em ordem

### Mudança 1 — memórias de array 2-D para 1-D

**Problema.** O cocotb não conseguia ler resultado nenhum da RAM.

```vhdl
-- ANTES: 2-D, um elemento por byte
type DATA_RAM_MEMORY_ARRAY_t is
    array (0 to N-1, 3 downto 0) of std_logic_vector(7 downto 0);

-- DEPOIS: 1-D, um elemento por palavra
type DATA_RAM_MEMORY_ARRAY_t is
    array (0 to N-1) of std_logic_vector(31 downto 0);
```

Motivo: **o VPI do GHDL não expõe arrays 2-D.**
`dut.data_memory.data_ram.memory` dava `AttributeError`. Já
`register_file.registers` (1-D) era lido sem problema. Verificado por execução.

Acessos de byte e halfword viraram fatias da palavra. Regras externas
preservadas: little-endian, alinhamento, `0xFFFFFFFF` em acesso inválido,
escrita fora de faixa descartada.

> **Armadilha que custou uma depuração.** A guarda de faixa e o índice do array
> **têm de ficar na mesma expressão condicional**. Quando separei a guarda num
> sinal próprio, ela passou a atrasar um delta em relação a `word_index`, e um
> endereço fora de faixa indexou o array antes de a guarda alcançar:
> `ghdl:error: index (1069604864) out of bounds (0 to 127)`.
> O design original já fazia certo; restaurei a estrutura dele.
>
> Arquivos: [`data_ram.vhd`](../examples/RISCV32I/src/data_ram.vhd),
> [`data_rom.vhd`](../examples/RISCV32I/src/data_rom.vhd),
> [`memory_package.vhd`](../examples/RISCV32I/src/memory_package.vhd).

### Mudança 2 — ROM carregável por arquivo `.ram`

**Problema.** Trocar de programa exigia rodar um Makefile, converter binário
para texto e **copiar e colar** dentro de `memory_package.vhd`. E o cocotb
**não consegue escrever na ROM**: `dut.instruction_memory.memory[0].value = ...`
é silenciosamente ignorado pelo VPI do GHDL — carregar em runtime está
descartado.

```vhdl
entity instruction_memory is
    generic(
        ROM_INIT_FILE   : string  := "";   -- ""  -> INSTRUCTION_MEMORY_CONTENT (original)
        ROM_SIZE_WORDS  : integer := 0     --  0  -> INSTRUCTION_MEMORY_SIZE_WORDS
    );
```

Preenchido, lê a imagem `.ram` por `textio` **na elaboração**. Formato
(uma palavra por linha, 8 dígitos hex, linha 0 = endereço `0x0`, `#` comenta)
documentado em ADR-003 e em
[`programs/README.md`](../examples/RISCV32I/programs/README.md).

Risco previsto no ADR-003 que **não se materializou**: `ghdl synth` aceita a
função com `textio` presente e retorna exit 0.

### Mudança 3 — a extensão RV32IM

É a mudança principal, e a que mais se aproveitou do que já existia.

---

## 4. Como a unidade M entrou sem mexer no pipeline

### O truque

As oito operações M foram **acrescentadas ao enum `ALU_OP_TYPE_t`** em vez de
virarem um sinal de controle novo:

```vhdl
type ALU_OP_TYPE_t is (ALU_OP_TYPE_ADD, ALU_OP_TYPE_SUB, ..., ALU_OP_TYPE_SRA,
                       -- RV32M
                       ALU_OP_TYPE_MUL, ALU_OP_TYPE_MULH, ALU_OP_TYPE_MULHSU,
                       ALU_OP_TYPE_MULHU, ALU_OP_TYPE_DIV, ALU_OP_TYPE_DIVU,
                       ALU_OP_TYPE_REM, ALU_OP_TYPE_REMU);
```

`alu_op_type` **já viajava** de Decode para Execute pelo
`decode_pipeline_register`. Logo o seletor da unidade M chega em EX por um
caminho que já existia — **nenhuma porta nova em registrador de pipeline.**

### Antes — estágio Execute

```
              rs1_e ──┐
                      ├──►  op1
   forwarding ────────┘
   (MEM→EX, WB→EX)
                             ┌───────────┐
                             │    ALU    │──► alu_result_e ──┬──► execute_pipeline_register
              rs2_e ──┐      └───────────┘                   │
                      ├──►  op2    ▲                         └──► branching_unit
   imm_e ─────────────┘            │
                            alu_op_type_e
                        (vem do decode_pipeline_register)
```

### Depois — a unidade M em paralelo, mux no fim

```
              rs1_e ──┐
                      ├──►  op1 ──┬──────────────┐
   forwarding ────────┘           │              │
   (MEM→EX, WB→EX)                ▼              ▼
                          ┌───────────┐  ┌────────────────┐
                          │    ALU    │  │  mul_div_unit  │   ◄── NOVO
                          └─────┬─────┘  └───────┬────────┘       (generate:
              rs2_e ──┐         │                │                 só quando
                      ├──► op2 ─┴────────────────┘                 RV32M_ENABLE)
   imm_e ─────────────┘   alu_core_result_e   m_result_e
                                 │                │
                                 └──►  ( mux )  ◄─┘
                                          ▲
                                  m_op_e = is_rv32m_op(alu_op_type_e)
                                          │
                                          ▼
                                    alu_result_e ──┬──► execute_pipeline_register
                                                   └──► branching_unit
```

O resultado da unidade M entra **no mesmo fio** `alu_result_e` de onde o
forwarding MEM→EX e WB→EX já partia. Por isso instruções M ganham forwarding
sem uma linha de código nova — e por isso `hazard_control_unit.vhd` não mudou.

### O que isso custou em arquivos

| Bloco | Mudou? | O quê |
|---|---|---|
| `cpu_package.vhd` | sim | 8 valores no enum + `funct3`/`funct7` + `is_rv32m_op` |
| `control_unit.vhd` | sim | generic `RV32M_ENABLE`; decodifica `funct7 = 0000001` |
| `instruction_decoder.vhd` | sim | `funct7 = 0000001` deixa de ser instrução inválida |
| `CPU.vhd` | sim | instancia a unidade em `generate`, mux, sinal `m_dispatch_e` |
| `mul_div_unit.vhd` | **novo** | as oito instruções |
| **4 registradores de pipeline** | **não** | — |
| **`hazard_control_unit.vhd`** | **não** | — |
| **`ALU.vhd`** | **não** | o `when others` final já cobre os valores novos |

### Por que combinacional

Latência de 1 ciclo, igual à ALU. **Não introduz stall nenhum**, então não há
nova condição de hazard a tratar — e é por isso que a lista acima tem tantos
"não".

O preço não é em ciclos, é em área e caminho crítico:

| | RV32I | RV32IM |
|---|---:|---:|
| células de lógica do núcleo | 6.239 | **56.327** (9,03×) |
| profundidade lógica em EX | 36 níveis (ALU) | **631** (`mul_div_unit`) |

A alternativa — unidade iterativa multiciclo — exigiria porta `stall` no
`decode_pipeline_register` e reescrita da precedência stall/flush/carga na
unidade de hazard. Registrada como trabalho futuro no ADR-007, com o custo já
levantado.

---

## 5. Uma correção que não era da CPU

O harness detectava fim de programa contando visitas do **PC de busca** ao
endereço do auto-laço. Está errado, e produzia resultado errado com hardware
correto.

A CPU é *always-not-taken* e resolve saltos só em EX. Num laço:

```
loop:  bge  x6, x7, fim
       ...
       j    loop           ◄── só resolvido em EX...
fim:   sw   x5, 0(x11)     ◄── ...depois que pc_f JÁ buscou aqui
halt:  j    halt           ◄── ...e AQUI, especulativamente
```

`pc_f` passa pelo endereço de parada **uma vez por iteração**. O teste
"soma 1..10 = 55" parava na 4ª iteração e dava 6.

**Correção (ADR-008):** detectar no *commit*, não na busca —
`pc_e == halt_pc and jump_e = '1'`. O flush zera `jump_out`, então uma bolha
nunca satisfaz a condição.

A fórmula de contagem de instruções também estava errada, descontando duas
vezes os ciclos de stall de load-use:

```
antes:   fetches - flush_d
depois:  fetches - flush_f - (flush_d - stalls)
```

---

## 6. O que foi acrescentado do zero

| Onde | O quê |
|---|---|
| `tools/rv_assembler.py` | montador RV32I/RV32IM (não há compilador RISC-V no ambiente) |
| `tools/build_programs.py` | `.asm` → imagem `.ram` |
| `tools/synth_ppa.py` | área e profundidade lógica por síntese real |
| `tools/bench_compare.py` | comparação de eficiência, com equivalência de RAM conferida antes |
| `test/rv_harness.py` | harness cocotb: clock, reset, término, métricas |
| `test/reference_model.py` | modelo de referência RV32I/RV32M em Python |
| `test/test_*.py` | 7 suítes, 795 passed / 26 skipped |
| `programs/` | 4 benchmarks × (`.c` + 2 `.asm` + 2 `.ram`) |
| `specs/decisions.md` | ADR-000 a ADR-009 |

---

## 7. Dois documentos antigos que ficaram desatualizados

Deixados como estavam — o princípio 8 diz para não remover — mas **enganam quem
ler agora**:

1. **`docs/mapa-do-projeto.html`** — "Onde o projeto está agora" e "Status por
   fase", cobrindo só as fases 0–7 da trilha A. **Zero menções a RISC-V.**
2. **`examples/RISCV32I/README.md`** — README do autor original. Descreve o
   fluxo antigo: rodar o Makefile, converter binário e *copiar e colar* dentro
   de `memory_package.vhd`. Substituído pelo `.ram` via generic, mas o texto
   não avisa.
3. **`examples/RISCV32I/CPU_tb.vhd`** — nunca rodou (literais `5ns`, `12ns`,
   `1ms` sem espaço, ilegais em VHDL). Substituído pelo fluxo cocotb;
   preservado, mas não consertado.

---

## 8. Os nove commits

| Commit | O quê |
|---|---|
| `732afa2` | specs: Emenda 1, FR-RV-01..25, plano RV-0..6, ADRs 000–009 |
| `54953b6` | memórias observáveis + ROM carregável por `.ram` |
| `4ae8c9b` | harness cocotb, montador, baseline RV32I verificada |
| `28b0a3f` | **extensão RV32IM sob `RV32M_ENABLE`** |
| `8ab1847` | comparação de eficiência medida no GHDL |
| `9a92278` | benchmarks `.c`/`.asm`/`.ram` |
| `206a813` | suíte completa RV32M — 92 casos |
| `d0f97ce` | relatório final + README com as duas trilhas |
| `1185a7e` | 38 tarefas fechadas com evidência de execução |
