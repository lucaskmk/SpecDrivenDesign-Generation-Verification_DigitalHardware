## Publica — incremento 6

Behavior: A valid RV32I load instruction decodes combinational controls for effective-address addition using the register base and immediate offset, enables register writeback from data memory, and keeps store, branch, jump, and multiply-divide controls inactive.
Coverage gap: Load instruction class control decoding and data-memory writeback selection
Prerequisites: Register-immediate ALU addition and immediate operand selection witnessed by smoke_test; Combinational full-tuple control decoding witnessed by test_decoder_smoke and op_add_register_decode
New factor: Selection of the data-memory read result on wb_select for a load instruction
Stimulus: A single legal RV32I load instruction with a destination register, a base register, and a signed immediate offset applied to the instruction input port.
Support/witness path: Direct combinational observation through the declared output ports of decoder; no support sequence is required because the decoder has no state.
Public observations: reg_write is asserted while mem_write remains deasserted; alu_src_a_pc is deasserted while alu_src_b_imm is asserted for immediate offset addition; alu_control selects addition and muldiv_op remains at its default non-M value; branch_enable, jump, and jalr remain deasserted; wb_select selects the data-memory read result
Forbidden: Inspecting internal decoder signals outside declared entity ports; Introducing clock or reset stimulus on a purely combinational entity; Using reserved, illegal, or malformed instruction encodings rejected by assemble_rv32im; Testing multiple instruction classes within this single focal case

## Publica — incremento 7

Behavior: When given a valid RV32IM store instruction, the combinational decoder asserts mem_write, deasserts reg_write, selects rs1 as ALU operand A, selects the immediate as ALU operand B, selects ADD on alu_control, keeps muldiv_op at its default zero encoding, deasserts branch_enable, jump, and jalr, and drives wb_select to its default ALU writeback encoding.
Coverage gap: Stores instruction class control decoding
Prerequisites: Combinational decoding of single RV32IM instructions on public ports; Immediate-offset address calculation operand selection witnessed by load instruction decoding
New factor: Store instruction class memory-write control decoding
Stimulus: Present a single legal RV32IM store instruction with non-zero source registers and a signed immediate offset at the instruction input of the combinational decoder.
Support/witness path: Direct observation on the declared combinational output ports; no support sequence is required.
Public observations: mem_write is asserted; reg_write is deasserted; alu_src_a_pc is deasserted to select rs1; alu_src_b_imm is asserted to select the immediate; alu_control selects ADD; muldiv_op outputs its default zero encoding; branch_enable is deasserted; jump is deasserted; jalr is deasserted; wb_select outputs its default ALU-result encoding
Forbidden: Accessing internal hierarchy or non-port signals; Using illegal, reserved, or unallocated instruction encodings; Combining multiple instruction classes within this focal case

## Publica — incremento 8

Behavior: When instr encodes a valid RV32M OP-M instruction with a non-zero M-operation selector, decoder combinationally asserts reg_write, selects M-unit writeback on wb_select, forwards the instruction function selector on muldiv_op, keeps alu_control at ADD, and deasserts mem_write, alu_src_a_pc, alu_src_b_imm, branch_enable, jump, and jalr.
Coverage gap: RV32M OP-M instruction class decoding in Behavior and Test strategy item 3 (M-extension writeback selection and non-zero muldiv_op forwarding)
Prerequisites: Combinational RV32I R-type OP decoding on the shared register-register opcode (op_add_register_decode, sub_register_decode_test)
New factor: RV32M M-extension R-type instruction decoding
Stimulus: Combinationally present a single legal RV32M extension register-register instruction that selects a non-zero M-unit operation.
Support/witness path: None required; decoder is purely combinational and every decoded control signal is directly observable on the declared output ports from the focal instruction alone.
Public observations: reg_write equals 1; mem_write equals 0; alu_src_a_pc equals 0; alu_src_b_imm equals 0; alu_control equals the ADD selector (zero); muldiv_op equals the non-zero selector corresponding to the chosen RV32M operation; branch_enable equals 0; jump equals 0; jalr equals 0; wb_select equals the M-unit writeback selector (three)
Forbidden: Reading or asserting internal DUT signals or hierarchy; Starting a clock or driving any non-existent reset port; Selecting MUL whose zero muldiv_op value is indistinguishable from the non-RV32M default; Driving reserved, illegal, or malformed encodings not expressible as legal RV32IM assembly; Testing multiple instruction classes in the same test case

## Publica — incremento 9

Behavior: Decode a canonical conditional branch instruction into `branch_enable='1'`, no register or memory write, register operand selection (`alu_src_a_pc='0'`, `alu_src_b_imm='0'`), the corresponding branch-condition `alu_control`, `muldiv_op="000"`, no unconditional jump controls, and `wb_select="00"`.
Coverage gap: Conditional branches instruction class (`0x63`) asserting `branch_enable` and selecting branch-condition `alu_control`
Prerequisites: Combinational decode of 32-bit RV32IM instruction words into the full control output tuple without clock or reset
New factor: Conditional branch opcode class (`branch_enable` assertion with branch-condition `alu_control` encoding)
Stimulus: Drive a single legal RV32I conditional branch instruction assembled from legal assembly source (using non-zero source registers, a non-zero branch target offset, and a non-BEQ branch condition so branch-condition `alu_control` selection is observable as distinct from default zero) onto `instr` and allow combinational outputs to settle.
Support/witness path: Direct combinational observation on public ports; no support sequence is required because `decoder` is stateless and all control signals are top-level outputs.
Public observations: `branch_enable` settles to `'1'`; `alu_control` settles to the four-bit branch-condition code corresponding to the chosen conditional branch `funct3`; `reg_write`, `mem_write`, `alu_src_a_pc`, `alu_src_b_imm`, `jump`, and `jalr` settle to `'0'`; `muldiv_op` settles to `"000"` and `wb_select` settles to `"00"`
Forbidden: Do not drive illegal, reserved, or malformed instruction words that cannot be produced by `assemble_rv32im`; Do not access internal signals or hierarchy attributes; Do not introduce clock or reset stimulus; Do not combine multiple instruction classes in this focal test

