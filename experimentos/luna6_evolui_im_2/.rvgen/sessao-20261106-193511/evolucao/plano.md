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

The ISA changes from RV32I to RV32IM. The existing RV32I datapath, interfaces, and behavior remain valid; the CPU must additionally recognize opcode 0x33 with funct7 0x01 and write the correct MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, or REMU result in the same single-cycle instruction. Division by zero and signed division overflow must follow the specified RISC-V results. The smallest change is to update the decoder to enable register writes for valid M encodings, then have the CPU select a combinational M result for writeback. The ALU and other existing blocks can remain unchanged.

## Blocos que mudam

- `decoder`: Recognize opcode 0x33 with funct7 0x01 and any funct3 from 000 through 111 as valid register-writing instructions. Use the existing OP register-write and operand-source controls, with a neutral ALU selector such as ADD because the CPU will bypass the ALU result for M instructions. Preserve the existing RV32I decoding and unsupported-encoding behavior.
- `cpu`: Keep the fixed public ports and existing instances. Add combinational M-operation detection and result generation for opcode 0x33/funct7 0x01, selecting the operation by funct3. Use the M result instead of the ALU result for writeback on these instructions, while retaining the decoder's register-write enable and the register file's x0 behavior. Compute full-width products for the high-half variants, including signed-by-unsigned MULHSU; implement signed and unsigned division/remainder with explicit divide-by-zero handling and signed overflow handling before division. Keep execution single-cycle.

## Blocos congelados

- `immediate_generator`
- `register_file`
- `alu`
