# Especificacao funcional - ULA MIPS de 32 bits

## Escopo

ULA puramente combinacional para o datapath MIPS classico. A especificacao
adota os codigos `ALUControl` convencionais do livro Patterson e Hennessy.

## Interface

| Porta | Direcao | Largura | Descricao |
|---|---:|---:|---|
| `a` | entrada | 32 | Primeiro operando sem sinal; interpretado como complemento de dois em `SLT`. |
| `b` | entrada | 32 | Segundo operando sem sinal; interpretado como complemento de dois em `SLT`. |
| `alu_control` | entrada | 4 | Seletor da operacao. |
| `result` | saida | 32 | Resultado da operacao selecionada. |
| `zero` | saida | 1 | `1` quando `result` e zero; caso contrario, `0`. |

## Requisitos funcionais

- **FR-01**: THE ULA SHALL accept two 32-bit operands named `a` and `b` and a
  4-bit control input named `alu_control`.
- **FR-02**: WHEN `alu_control = 0000`, THE ULA SHALL set `result` to `a AND b`.
- **FR-03**: WHEN `alu_control = 0001`, THE ULA SHALL set `result` to `a OR b`.
- **FR-04**: WHEN `alu_control = 0010`, THE ULA SHALL set `result` to the
  32-bit two's-complement sum `a + b`.
- **FR-05**: WHEN `alu_control = 0110`, THE ULA SHALL set `result` to the
  32-bit two's-complement difference `a - b`.
- **FR-06**: WHEN `alu_control = 0111`, THE ULA SHALL set bit zero of `result`
  to `1` if signed(`a`) is less than signed(`b`), and SHALL clear every other
  result bit; otherwise it SHALL clear `result`.
- **FR-07**: WHEN `alu_control = 1100`, THE ULA SHALL set `result` to `a NOR b`.
- **FR-08**: THE ULA SHALL set `zero` when and only when `result` equals zero.
- **FR-09**: WHEN `alu_control` is unsupported, THE ULA SHALL drive `result`
  to zero and therefore drive `zero` to `1`.

## Requisitos nao funcionais

- **NFR-01**: THE ULA SHALL be purely combinational, with no clock, state, or
  storage elements.
- **NFR-02**: THE ULA SHALL use IEEE `numeric_std` for signed arithmetic and
  comparison, avoiding non-standard arithmetic packages.
- **NFR-03**: THE generated implementation and testbench SHALL retain
  requirement identifiers for traceability.
