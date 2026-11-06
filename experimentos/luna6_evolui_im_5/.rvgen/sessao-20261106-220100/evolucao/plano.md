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

The CPU specification changes from RV32I to RV32IM while remaining single-cycle and retaining the same fixed top-level cpu interface. All RV32I behavior and public bus semantics remain required. The new instructions are R-type OP encodings with funct7 = 0000001; they must produce results in the same cycle, including defined divide-by-zero and signed-overflow results. The approved RV32I baseline does not establish M-extension support. Preserve the already-correct immediate generator, register file, and RV32I ALU; extend the decoder to recognize valid M encodings and add a combinational multiply/divide unit. Update the CPU to connect these blocks and select M results for writeback without changing the top-level ports.

## Decomposição-alvo

| Bloco | Ação | De | O que muda |
|---|---|---|---|
| `immediate_generator` | mantido (congelado) | immediate_generator | No change. Its RV32I immediate generation remains correct for RV32IM. |
| `register_file` | mantido (congelado) | register_file | No change. The existing 32-register file, asynchronous reads, rising-edge writes, reset, and hardwired x0 behavior apply equally to RV32IM. |
| `alu` | mantido (congelado) | alu | No change. This block continues to implement the existing RV32I operations; M operations are handled by a separate block. |
| `decoder` | muda | decoder | Extend OP decoding to recognize funct7 = 0000001 and all eight funct3 values as valid M instructions. Assert reg_write and a new m_enable output for those encodings, with register operands selected. Preserve all existing RV32I decoding and no-side-effect behavior for unsupported encodings. |
| `muldiv` | novo | - | Add a purely combinational RV32M execution block implementing MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, and REMU. |
| `cpu` | muda | cpu | Keep the exact existing top-level entity and ports. Integrate the changed decoder and one muldiv instance; route rs1, rs2, and instr funct3 to the M unit; select its result for writeback when m_enable is asserted. Preserve the existing RV32I datapath, reset behavior, PC sequencing, memory interface, and one-instruction-per-edge execution. |

## Removidos

- (nenhum)
