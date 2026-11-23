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
