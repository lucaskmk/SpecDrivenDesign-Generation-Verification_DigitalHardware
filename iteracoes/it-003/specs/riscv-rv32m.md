# RV32M — referência de implementação

Fonte: RISC-V Unprivileged ISA, extensão "M" para multiplicação e divisão
inteiras, versão 2.0 (RISC-V International, CC-BY-4.0).

Este arquivo só vale quando `specs/cpu.md` declara **RV32IM**. Ele completa
`riscv-rv32i.md`, que continua valendo inteiro: RV32IM = RV32I + M. Com
**RV32I** este arquivo não vai para a IA e a CPU não implementa nenhuma
instrução abaixo.

## Codificação

Todas as instruções M são R-type, com `opcode = 0110011` (`0x33`, o mesmo do
OP do RV32I) e `funct7 = 0000001` (`0x01`). O `funct7` é o que separa M de
ADD/SUB/shifts/lógica: no RV32I ele vale `0x00` ou `0x20`.

| Instrução | `funct3` | `funct7` | Resultado em `rd` |
|---|---:|---:|---|
| MUL | `0x0` | `0x01` | 32 bits baixos de `rs1 × rs2` |
| MULH | `0x1` | `0x01` | 32 bits altos de `signed(rs1) × signed(rs2)` |
| MULHSU | `0x2` | `0x01` | 32 bits altos de `signed(rs1) × unsigned(rs2)` |
| MULHU | `0x3` | `0x01` | 32 bits altos de `unsigned(rs1) × unsigned(rs2)` |
| DIV | `0x4` | `0x01` | quociente signed, arredondado para zero |
| DIVU | `0x5` | `0x01` | quociente unsigned |
| REM | `0x6` | `0x01` | resto signed; o sinal é o do dividendo (`rs1`) |
| REMU | `0x7` | `0x01` | resto unsigned |

## Regras gerais

- O produto completo tem 64 bits. MUL devolve os bits `[31:0]` e é o mesmo
  para operandos signed ou unsigned. MULH, MULHSU e MULHU devolvem os bits
  `[63:32]`.
- MULHSU trata `rs1` como signed e `rs2` como unsigned. Não troque a ordem.
- Divisão e resto truncam para zero: `-7 / 2 = -3` e `-7 rem 2 = -1`.
- Nenhuma instrução M gera exceção, trap ou estado extra. `rd = x0` continua
  sendo ignorado.
- No contrato monociclo de `specs/cpu.md`, uma instrução completa por borda de
  subida: o resultado de MUL e DIV precisa estar pronto no mesmo ciclo.

## Casos especiais obrigatórios

A divisão por zero e o overflow têm resultado definido pela ISA. A CPU deve
produzir exatamente estes valores (`x` é o dividendo `rs1`):

| Caso | DIV | DIVU | REM | REMU |
|---|---|---|---|---|
| divisor = 0 | `-1` (`0xFFFFFFFF`) | `2^32 - 1` (`0xFFFFFFFF`) | `x` | `x` |
| overflow: `x = -2^31` (`0x80000000`) e divisor = `-1` | `-2^31` (`0x80000000`) | (não se aplica) | `0` | (não se aplica) |

## Exemplos para conferir

| Instrução | `rs1` | `rs2` | `rd` |
|---|---|---|---|
| MUL | `0x00000007` | `0xFFFFFFFD` (-3) | `0xFFFFFFEB` (-21) |
| MULH | `0x80000000` | `0x80000000` | `0x40000000` |
| MULHSU | `0xFFFFFFFF` (-1) | `0xFFFFFFFF` | `0xFFFFFFFF` |
| MULHU | `0xFFFFFFFF` | `0xFFFFFFFF` | `0xFFFFFFFE` |
| DIV | `0xFFFFFFF9` (-7) | `0x00000002` | `0xFFFFFFFD` (-3) |
| DIVU | `0xFFFFFFF9` | `0x00000002` | `0x7FFFFFFC` |
| REM | `0xFFFFFFF9` (-7) | `0x00000002` | `0xFFFFFFFF` (-1) |
| REMU | `0xFFFFFFF9` | `0x00000002` | `0x00000001` |
| DIV | `0x00000005` | `0x00000000` | `0xFFFFFFFF` |
| REM | `0x00000005` | `0x00000000` | `0x00000005` |
| DIV | `0x80000000` | `0xFFFFFFFF` (-1) | `0x80000000` |
| REM | `0x80000000` | `0xFFFFFFFF` (-1) | `0x00000000` |

## Notas para VHDL (`numeric_std`)

- `signed(a) * signed(b)` com operandos de 32 bits dá 64 bits. Para MULHSU,
  estenda `rs1` com sinal e `rs2` com zero até 33 bits, multiplique como
  `signed` (66 bits) e pegue os bits `[63:32]`.
- `/` e `rem` de `numeric_std` truncam para zero e dão ao resto o sinal do
  dividendo, como a ISA. Mas dividir por zero em VHDL para a simulação com
  erro: trate divisor zero e o overflow **antes** de calcular, com as saídas
  da tabela de casos especiais.
