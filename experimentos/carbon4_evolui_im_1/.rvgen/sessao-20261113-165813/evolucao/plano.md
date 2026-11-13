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

The CPU specification changed from single-cycle RV32I to single-cycle RV32IM while keeping the exact same top-level entity, single-cycle execution timing, memory bus protocol, and asynchronous active-high reset. The CPU must now decode and execute the eight R-type M-extension instructions (MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, REMU) encoded under opcode 0110011 (0x33) with funct7 = 0000001 (0x01) in a single clock cycle, including exact RISC-V architectural results for division by zero and signed division overflow (-2^31 / -1) guarded before VHDL division/remainder operators.

## Decomposição-alvo

| Bloco | Ação | De | O que muda |
|---|---|---|---|
| `immediate_generator` | mantido (congelado) | immediate_generator | kept |
| `register_file` | mantido (congelado) | register_file | kept |
| `alu` | mantido (congelado) | alu | kept |
| `muldiv_unit` | novo | - | New combinational execution unit implementing the eight RV32M multiply, divide, and remainder operations. |
| `decoder` | muda | decoder | Decode opcode 0x33 with funct7 = 0000001 as valid RV32M instructions, add the 3-bit muldiv_op output, and use wb_select = "11" to select muldiv_unit writeback. |
| `cpu` | muda | cpu | Instantiate muldiv_unit, connect rs1_data, rs2_data, and decoder muldiv_op to it, and select muldiv_unit result for register writeback when wb_select = "11". |

## Removidos

- (nenhum)
