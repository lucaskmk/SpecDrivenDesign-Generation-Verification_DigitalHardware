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

The specification changes the CPU from RV32I to RV32IM, so all eight RV32M operations must now complete in the existing single-cycle timing model. The public cpu interface, reset behavior, memory contract, and RV32I semantics remain unchanged. The existing immediate generator, register file, ALU, and decoder remain correctly scoped: the decoder already treats funct7=0000001 OP encodings as unsupported, so a separate RV32M unit can recognize those encodings and produce a result without changing the approved RV32I blocks. The CPU must combine that unit's valid signal and result with the existing register-write and writeback paths. Division-by-zero and signed-overflow results must be handled explicitly in the RV32M unit.

## Decomposição-alvo

| Bloco | Ação | De | O que muda |
|---|---|---|---|
| `immediate_generator` | mantido (congelado) | immediate_generator | No change. The existing immediate generation contract is identical in RV32IM. |
| `register_file` | mantido (congelado) | register_file | No change. The existing 32-register state, asynchronous reads, reset, and x0 behavior remain sufficient. |
| `alu` | mantido (congelado) | alu | No change. It continues to implement the approved RV32I operations; RV32M arithmetic is handled by a separate unit. |
| `decoder` | mantido (congelado) | decoder | No change. Its existing RV32I decode remains valid; M encodings remain unsupported by this decoder and are recognized by rv32m_unit. |
| `rv32m_unit` | novo | - | Add combinational decode and execution for opcode 0110011 with funct7 0000001, including all eight RV32M operations and their required division corner cases. |
| `cpu` | muda | cpu | Integrate one rv32m_unit while preserving the fixed top-level ports and existing RV32I datapaths. Use the unit's valid signal to enable register writes for M instructions and select its result for writeback; retain the existing decoder controls for RV32I instructions. Preserve reset suppression of stores and execution, PC sequencing, and all existing RV32I behavior. |

## Removidos

- (nenhum)
