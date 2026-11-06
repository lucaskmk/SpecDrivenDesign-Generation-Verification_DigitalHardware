# Plano de evolução: RV32I -> RV32IM

Origem: `/repo/experimentos/luna6_prof_3`

## Linha de base (antes de mudar)

- spec-riscv-test (rv32i): 40/40 casos
- immediate_generator: 5/5 teste(s) de componente ok
- register_file: 5/5 teste(s) de componente ok
- alu: 5/5 teste(s) de componente ok
- decoder: 5/5 teste(s) de componente ok
- cpu: 5/5 teste(s) de componente ok

## Entendimento da IA

The CPU changes from RV32I to RV32IM; the existing RV32I datapath and external interface remain unchanged. The new OP encodings use opcode 0x33 and funct7 0x01, with funct3 selecting one of eight multiply, divide, or remainder operations. The decoder must recognize these encodings as valid register-writing instructions, and the CPU must route their results to register writeback. Division must implement the specified divide-by-zero and signed-overflow results. No changes are needed to the immediate generator, register file, or existing RV32I ALU.

## Blocos que mudam

- `decoder`: Recognize opcode 0x33 with funct7 0x01 and any funct3 as a valid OP instruction: assert reg_write, select register operands, use wb_select "00", and leave memory, branch, and jump controls inactive. The ALU selector can be set to a harmless default because the CPU will select the RV32M result for these encodings. Preserve existing RV32I decoding and ensure other unsupported OP encodings still have no side effects.
- `cpu`: Keep the fixed public ports and existing RV32I behavior. Instantiate the new RV32M unit, feed it the register-file operands and instr[14:12], and select its result for writeback when opcode is 0x33 and instr[31:25] is 0x01. Use the decoder's register-write control for valid M instructions; retain existing writeback behavior for all other instructions.
- `rv32m`: new block

## Blocos congelados

- `immediate_generator`
- `register_file`
- `alu`
