# RV32I — referência de implementação

Fonte: RISC-V Unprivileged ISA, RV32I v2.1. Derivada de
`specs/upstream/riscv-rv32i.adoc` (RISC-V International, CC-BY-4.0).

Este perfil é deliberadamente limitado ao contrato deste projeto: não inclui
FENCE, ECALL, EBREAK, CSRs, interrupções nem acessos desalinhados.

## Estado e regras gerais

- `XLEN = 32`; todo resultado aritmético é reduzido a 32 bits. Não há exceção
  de overflow para aritmética inteira.
- Há 32 registradores `x0` a `x31`; `x0` sempre lê como zero e toda escrita em
  `x0` é ignorada.
- `pc` é o endereço da instrução atual. Instruções são palavras de 32 bits,
  alinhadas em quatro bytes. A instrução sequencial seguinte fica em `pc + 4`.
- Imediatos I, S, B e J são sign-extended a 32 bits a partir de `instr(31)`.
- A memória é endereçada por byte e little-endian. A CPU pode assumir que todo
  acesso de byte, meia palavra ou palavra recebido pelo validador é alinhado.

## Campos e imediatos

```text
opcode = instr[6:0]      rd = instr[11:7]
funct3 = instr[14:12]    rs1 = instr[19:15]    rs2 = instr[24:20]
funct7 = instr[31:25]

I = sext(instr[31:20])
S = sext(instr[31:25] || instr[11:7])
B = sext(instr[31] || instr[7] || instr[30:25] || instr[11:8] || 0)
U = instr[31:12] || 12'b0
J = sext(instr[31] || instr[19:12] || instr[20] || instr[30:21] || 0)
```

### Formatos de instrução

Todo formato ocupa uma palavra de 32 bits. Os nomes abaixo descrevem a posição
dos campos na palavra; não são entidades VHDL obrigatórias nem impõem uma
microarquitetura.

| Formato | Layout de `instr[31:0]` | Usado por |
|---|---|---|
| R-type | `funct7 | rs2 | rs1 | funct3 | rd | opcode` | OP: `add`, `sub`, shifts, comparações e lógica entre registradores |
| I-type | `imm[11:0] | rs1 | funct3 | rd | opcode` | OP-IMM, loads e `jalr` |
| S-type | `imm[11:5] | rs2 | rs1 | funct3 | imm[4:0] | opcode` | stores |
| B-type (variante de S) | `imm[12|10:5] | rs2 | rs1 | funct3 | imm[4:1|11] | opcode` | branches condicionais |
| U-type | `imm[31:12] | rd | opcode` | `lui`, `auipc` |
| J-type (variante de U) | `imm[20|10:1|11|19:12] | rd | opcode` | `jal` |

Para eliminar dúvidas sobre campos repartidos:

- R-type: `rd=instr[11:7]`, `rs1=instr[19:15]`, `rs2=instr[24:20]`.
- I-type: `I=sext(instr[31:20])`; em shifts imediatos, `shamt=instr[24:20]`.
- S-type: `S=sext(instr[31:25] || instr[11:7])`.
- B-type e J-type sempre têm bit zero implícito: seus destinos são pares.
- U-type não recebe sign-extension: `U=instr[31:12] << 12`.
- `rd` é escrito apenas pelas instruções que o possuem. Branches e stores não
  escrevem registrador; `x0` jamais muda, mesmo quando aparece como `rd`.

### Mapeamento de bits dos imediatos

Esta tabela é a fonte direta para um gerador de imediatos. `inst[y:x]` significa
os bits da palavra de instrução original, antes de qualquer extração de campo.
Os intervalos superiores indicados como extensão de sinal repetem `inst[31]`.

| Imediato | Bits de saída | Origem exata |
|---|---|---|
| I | `imm[11:0]` | `inst[31:20]` |
| I | `imm[31:12]` | sinal: cópias de `inst[31]` |
| S | `imm[4:0]` | `inst[11:7]` |
| S | `imm[11:5]` | `inst[31:25]` |
| S | `imm[31:12]` | sinal: cópias de `inst[31]` |
| B | `imm[0]` | constante `0` |
| B | `imm[4:1]` | `inst[11:8]` |
| B | `imm[10:5]` | `inst[30:25]` |
| B | `imm[11]` | `inst[7]` |
| B | `imm[12]` e `imm[31:13]` | `inst[31]` e sua extensão de sinal |
| U | `imm[11:0]` | constantes `0` |
| U | `imm[31:12]` | `inst[31:12]` |
| J | `imm[0]` | constante `0` |
| J | `imm[10:1]` | `inst[30:21]` |
| J | `imm[11]` | `inst[20]` |
| J | `imm[19:12]` | `inst[19:12]` |
| J | `imm[20]` e `imm[31:21]` | `inst[31]` e sua extensão de sinal |

As variantes B e J preservam os campos de registradores e `funct3` dos formatos
S e U, respectivamente; somente redistribuem os bits do imediato para que o
bit menos significativo seja sempre zero. Não trate B como S nem J como U ao
montar o imediato: use as posições exatas desta tabela.

### Regra crítica: bit da instrução versus índice do campo

Quando um componente recebe o campo já extraído como:

```vhdl
funct7 : std_logic_vector(6 downto 0)  -- instr[31:25]
```

os índices VHDL não são os números dos bits da instrução inteira:

| Bit da instrução | Índice em `funct7(6 downto 0)` |
|---:|---:|
| `instr[31]` | `funct7(6)` |
| `instr[30]` | `funct7(5)` |
| `instr[25]` | `funct7(0)` |

Portanto, `instr[30]` é `funct7(5)`. Nunca escreva `funct7(30)` em VHDL:
essa porta só possui índices de `6` até `0`.

## Codificação canônica de operações inteiras

As tabelas seguintes valem somente para um componente que escolha decodificar
diretamente `opcode`, `funct3` e `funct7`. Outra decomposição interna é livre,
mas não pode atribuir semântica RV32I diferente a esses campos.

### OP (R-type), `opcode = 0x33`

| Instrução | `funct3` | `funct7` | Regra |
|---|---:|---:|---|
| ADD | `0x0` | `0x00` | `rs1 + rs2` |
| SUB | `0x0` | `0x20` | `rs1 - rs2` |
| SLL | `0x1` | `0x00` | `rs1 << rs2[4:0]` |
| SLT | `0x2` | `0x00` | signed `rs1 < rs2` |
| SLTU | `0x3` | `0x00` | unsigned `rs1 < rs2` |
| XOR | `0x4` | `0x00` | `rs1 XOR rs2` |
| SRL | `0x5` | `0x00` | logical right shift |
| SRA | `0x5` | `0x20` | arithmetic right shift |
| OR | `0x6` | `0x00` | `rs1 OR rs2` |
| AND | `0x7` | `0x00` | `rs1 AND rs2` |

### OP-IMM (I-type), `opcode = 0x13`

| Instrução | `funct3` | Bits `instr[31:25]` | Regra |
|---|---:|---:|---|
| ADDI | `0x0` | não selecionam a operação | `rs1 + I` |
| SLTI | `0x2` | não selecionam a operação | signed `rs1 < I` |
| SLTIU | `0x3` | não selecionam a operação | unsigned `rs1 < I` |
| XORI | `0x4` | não selecionam a operação | `rs1 XOR I` |
| ORI | `0x6` | não selecionam a operação | `rs1 OR I` |
| ANDI | `0x7` | não selecionam a operação | `rs1 AND I` |
| SLLI | `0x1` | `0x00` | `rs1 << instr[24:20]` |
| SRLI | `0x5` | `0x00` | logical right shift |
| SRAI | `0x5` | `0x20` | arithmetic right shift |

Não invente distinções extras: `funct7` não distingue SLT de SLTU, nem OR de
AND. Em particular, `funct3=0x3` é SLTU, `0x5` é SRL/SRA, `0x6` é OR e `0x7`
é AND.

## Operações de registradores

`OP` usa opcode `0110011`; `OP-IMM` usa opcode `0010011`.

| Instrução | Resultado em `rd` |
|---|---|
| `add`, `addi` | `rs1 + rs2` ou `rs1 + I` |
| `sub` | `rs1 - rs2` |
| `sll`, `slli` | deslocamento lógico à esquerda por `rs2[4:0]` ou `shamt` |
| `srl`, `srli` | deslocamento lógico à direita |
| `sra`, `srai` | deslocamento aritmético à direita, preservando sinal |
| `slt`, `slti` | `1` se comparação signed for verdadeira; senão `0` |
| `sltu`, `sltiu` | `1` se comparação unsigned for verdadeira; senão `0` |
| `xor`, `xori` | XOR bit a bit |
| `or`, `ori` | OR bit a bit |
| `and`, `andi` | AND bit a bit |

Para shifts imediatos, `shamt = instr[24:20]`; `SRAI` é selecionado por
`instr[30] = 1`, enquanto `SRLI` tem `instr[30] = 0`.

## U e transferências de controle

| Instrução | Efeito |
|---|---|
| `lui rd,U` | `rd = U` |
| `auipc rd,U` | `rd = pc + U` |
| `jal rd,J` | `rd = pc + 4`; próximo `pc = pc + J` |
| `jalr rd,rs1,I` | `rd = pc + 4`; próximo `pc = (rs1 + I) & 0xFFFFFFFE` |
| `beq` / `bne` | desvia por `B` se os operandos são iguais / diferentes |
| `blt` / `bge` | desvia por `B` conforme comparação signed |
| `bltu` / `bgeu` | desvia por `B` conforme comparação unsigned |

Quando uma branch não desvia, o próximo `pc` é `pc + 4`. `jal x0, 0` é o laço
de parada usado pelo validador.

## Loads e stores

Endereço efetivo: `rs1 + I` para loads e `rs1 + S` para stores.

| Instrução | Efeito |
|---|---|
| `lb` | lê 8 bits e faz sign-extension para 32 bits |
| `lbu` | lê 8 bits e faz zero-extension |
| `lh` | lê 16 bits e faz sign-extension para 32 bits |
| `lhu` | lê 16 bits e faz zero-extension |
| `lw` | lê 32 bits |
| `sb` | escreve os 8 bits baixos de `rs2` |
| `sh` | escreve os 16 bits baixos de `rs2` |
| `sw` | escreve os 32 bits de `rs2` |

No barramento da CPU, `data_width` é `00` para byte, `01` para meia palavra e
`10` para palavra. A CPU deve selecionar o byte ou meia palavra usando os bits
baixos do endereço e aplicar extensão de sinal somente em `LB` e `LH`.
