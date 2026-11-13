# Plano de evolução: RV32I -> RV32IM

Origem: `experimentos/luna6_prof_3`

## Linha de base (antes de mudar)

- spec-riscv-test (rv32i): 40/40 casos
- immediate_generator: 5/5 teste(s) de componente ok
- register_file: 5/5 teste(s) de componente ok
- alu: 5/5 teste(s) de componente ok
- decoder: 5/5 teste(s) de componente ok
- cpu: 5/5 teste(s) de componente ok

## Entendimento da IA

The specification changes from single-cycle RV32I to single-cycle RV32IM. Eight register-register M instructions must be decoded and completed on the current instruction’s rising edge. Division by zero and signed-division overflow have defined results. The CPU’s external interface and all RV32I behavior remain unchanged.

## Decomposição-alvo

| Bloco | Ação | De | O que muda |
|---|---|---|---|
| `immediate_generator` | muda | immediate_generator | Retain the five immediate formulas, but review and validate the block as part of the RV32IM decomposition. M instructions introduce no immediate format. |
| `register_file` | mantido (congelado) | register_file | None. |
| `alu` | mantido (congelado) | alu | None. |
| `m_unit` | novo | - | Add combinational execution of MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, and REMU. |
| `decoder` | muda | decoder | Add m_enable for OP instructions with funct7=0000001 and any of the eight funct3 values. Retain RV32I decoding and unsupported-instruction behavior. |
| `cpu` | muda | cpu | Instantiate m_unit and select its result for register writeback when m_enable is asserted. Preserve existing PC, RV32I datapath, reset, and external-bus behavior. |

## Removidos

- (nenhum)
