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

The contract moves from RV32I to RV32IM, single cycle. The new instructions share opcode 0x33 and use funct7 = 0000001: mul, mulh, mulhsu, mulhu, div, divu, rem, remu. Their results must be ready in the same cycle, so they are combinational. This includes the divide-by-zero (DIV/DIVU = 0xFFFFFFFF, REM/REMU = rs1) and signed-overflow (0x80000000 / -1: DIV = 0x80000000, REM = 0) semantics. The bus contract, PC, reset, immediates, register file and the existing ALU are unaffected. The ALU already passed its tests and stays frozen. Three things change. (1) The decoder currently treats funct7 = 0000001 on OP as unsupported (no side effects), so it must now accept it and flag it as an M instruction. (2) A multiply/divide datapath must be added; it is split into a multiplier, a divider with the special cases, and a small selector block, each verifiable on its own. (3) The cpu must instantiate that datapath and add an M-result source to the writeback mux. The entity stays without generics.

## Decomposição-alvo

| Bloco | Ação | De | O que muda |
|---|---|---|---|
| `immediate_generator` | mantido (congelado) | immediate_generator | No change. The immediates are identical in RV32IM. |
| `register_file` | mantido (congelado) | register_file | No change. M instructions use the same two read ports and one write port. |
| `alu` | mantido (congelado) | alu | No change. Multiply and divide go into separate blocks so the approved ALU contract and its tests stay frozen. For M instructions the ALU result is simply not selected. |
| `multiplier` | novo | - | New combinational 32x32 multiplier for MUL, MULH, MULHSU and MULHU. |
| `divider` | novo | - | New combinational divider/remainder unit for DIV, DIVU, REM and REMU with ISA special cases. |
| `muldiv_unit` | novo | - | New wrapper that selects between the multiplier and the divider by funct3. |
| `decoder` | muda | decoder | Add an output muldiv_op. For opcode 0x33 with funct7 = 0000001, all eight funct3 values are now valid: reg_write = 1, mem_write = 0, alu_src_a_pc = 0, alu_src_b_imm = 0, branch_enable = 0, jump = 0, jalr = 0, alu_control = 0000, wb_select = 00, muldiv_op = 1. muldiv_op is 0 for every other instruction, including unsupported ones. All previous encodings and the unsupported-instruction behavior (now also with muldiv_op = 0) stay identical. Only OP funct7 values other than 0000000, 0100000 (where valid) and 0000001 remain unsupported. wb_select = 11 stays reserved. |
| `cpu` | muda | cpu | Instantiate muldiv_unit with rs1_data, rs2_data and instr(14 downto 12), and connect the decoder's muldiv_op. The writeback mux gains a fourth source: when muldiv_op = '1' the register write data is the muldiv_unit result, otherwise the existing wb_select mux (ALU, load data, PC+4) applies. PC logic, branch evaluation, load extraction, store routing, data_write, reset and the ALU adaptation stay unchanged. The ports are unchanged and there are no generics. |

## Removidos

- (nenhum)
