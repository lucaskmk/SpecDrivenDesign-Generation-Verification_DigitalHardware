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

The contract goes from RV32I to RV32IM. The entity `cpu` and its ports do not change. The only new behaviour is opcode 0110011 with funct7 = 0000001 (mul, mulh, mulhsu, mulhu, div, divu, rem, remu). It must complete combinationally in the same single cycle, with the ISA's division-by-zero and signed-overflow results (x/0 gives -1 for div and divu, and gives x for rem and remu; 0x80000000 / -1 gives 0x80000000 for div and 0 for rem). The immediate generator, register file and ALU are unaffected, because M instructions use rs1 and rs2 and write rd through the existing paths. Three things must change. The decoder currently treats funct7 = 0000001 on OP as unsupported (no side effects), so it must recognise M and tell the CPU. A new arithmetic unit is needed for the products and quotients. The CPU must add that result to the writeback mux. To preserve the 40/40 baseline and keep verification localized, the approved blocks stay frozen and M is added as isolated, separately testable blocks: a multiplier, a divider, and a thin selector wrapper. The decoder signals M through the previously reserved wb_select = "11" plus a 3-bit M operation output. For an M instruction the decoder drives reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=0, alu_control="0000", branch_enable=0, jump=0, jalr=0, wb_select="11", and muldiv_op=funct3. For every other instruction muldiv_op is "000". The existing OP funct7 values 0000000 and 0100000 and all other decodes are unchanged, and unsupported funct7 values still give the no-side-effect tuple.

## Decomposição-alvo

| Bloco | Ação | De | O que muda |
|---|---|---|---|
| `immediate_generator` | mantido (congelado) | immediate_generator | No change: M instructions are R-type and use no new immediate. |
| `register_file` | mantido (congelado) | register_file | No change: M results are written through the same rd write port. |
| `alu` | mantido (congelado) | alu | No change: the RV32I ALU keeps its contract. M operations are kept out of it so its approved selector table and tests stay valid. |
| `multiplier` | novo | - | New combinational 32x32 multiplier for MUL, MULH, MULHSU, MULHU. |
| `divider` | novo | - | New combinational divider and remainder unit for DIV, DIVU, REM, REMU. |
| `muldiv_unit` | novo | - | New thin wrapper that decodes funct3 into multiplier or divider and returns a single M result. |
| `decoder` | muda | decoder | Accept OP with funct7=0000001 for every funct3 as a valid M instruction: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=0, alu_control="0000", branch_enable=0, jump=0, jalr=0, wb_select="11" (previously reserved, now selecting the M-unit result). Add the output muldiv_op (= funct3 for M instructions, "000" otherwise). All other encodings, including OP with funct7 other than 0000000, 0100000 and 0000001, keep their previous outputs. |
| `cpu` | muda | cpu | Instantiate muldiv_unit with rs1_data, rs2_data and the decoder's muldiv_op, and extend the writeback mux so wb_select="11" writes the M result. The fetch, PC, branch, jump, load/store and data-bus behaviour is unchanged. Entity and ports are unchanged, with no generics. M instructions leave data_write at '0' and the next PC at pc+4. |

## Removidos

- (nenhum)
