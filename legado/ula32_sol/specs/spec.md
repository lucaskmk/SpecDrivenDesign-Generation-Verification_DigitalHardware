# Especificacao da ULA de 32 bits

Status: aprovada pela selecao do usuario da interface MIPS-style.

## Interface

- `a`: operando de 32 bits.
- `b`: operando de 32 bits.
- `alu_control`: controle de 4 bits.
- `result`: resultado de 32 bits.
- `zero`: vale `1` exatamente quando `result` e zero.

## Requisitos funcionais

- **FR-01**: THE ULA SHALL ser um circuito puramente combinacional com dois
  operandos de 32 bits, controle de 4 bits, resultado de 32 bits e flag `zero`.
- **FR-02**: WHEN `alu_control` possui um codigo valido, THE ULA SHALL executar
  a operacao definida na tabela abaixo.
- **FR-03**: WHEN o resultado da operacao e `0x00000000`, THE ULA SHALL definir
  `zero = '1'`; OTHERWISE THE ULA SHALL definir `zero = '0'`.
- **FR-04**: WHEN `alu_control` nao corresponde a uma operacao definida, THE
  ULA SHALL produzir `result = 0x00000000` e `zero = '1'`.
- **FR-05**: WHEN uma soma ou subtracao excede 32 bits, THE ULA SHALL manter os
  32 bits menos significativos (aritmetica modular, sem flag de overflow).
- **FR-06**: WHEN a operacao SLT e selecionada, THE ULA SHALL comparar `a` e
  `b` como inteiros de 32 bits com sinal em complemento de dois.

## Codificacao das operacoes

| `alu_control` | Operacao | Expressao |
|---|---|---|
| `0000` | AND | `a and b` |
| `0001` | OR | `a or b` |
| `0010` | ADD | `a + b` |
| `0110` | SUB | `a - b` |
| `0111` | SLT signed | `1` se `signed(a) < signed(b)`, senao `0` |
| `1100` | NOR | `not (a or b)` |

## Requisitos nao funcionais

- **NFR-01 (velocidade)**: THE ULA SHALL usar logica combinacional, sem clock
  ou ciclos adicionais de latencia.
- **NFR-02 (area/portabilidade)**: THE ULA SHALL usar VHDL sintetizavel e tipos
  IEEE `numeric_std`, sem primitivas especificas de fabricante.
- **NFR-03 (verificacao)**: THE ULA SHALL possuir testbench cocotb rastreavel
  aos requisitos e executavel com GHDL por um unico comando `make -C test`.

## Fora de escopo

Flags de carry, overflow e negativo, operacoes de deslocamento, multiplicacao,
divisao, elementos sequenciais e interface com clock nao fazem parte desta ULA.
