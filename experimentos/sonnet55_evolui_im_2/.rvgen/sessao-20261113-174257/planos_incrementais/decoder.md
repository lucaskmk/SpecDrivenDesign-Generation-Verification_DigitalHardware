## Publica — incremento 6

Behavior: A legal store instruction (SW, funct3 word) decodes to the Stores row: reg_write=0, mem_write=1, alu_src_a_pc=0, alu_src_b_imm=1, alu_control=ADD (0x0), branch_enable=0, jump=0, jalr=0, wb_select=0x0, muldiv_op=0.
Coverage gap: Test strategy item 5 (stores): no public-port witness yet that a valid store asserts mem_write and deasserts reg_write. mem_write has only been observed at its default '0' in the existing cases.
Prerequisites: Whole-tuple observation of a decode (ADD, SUB, ADDI, M tuple). alu_src_b_imm=1 for an immediate-operand class (ADDI). Zero default for jump, jalr, branch_enable and muldiv_op (existing OP and OP-IMM witnesses). All of these already have passing witnesses.
New factor: Store opcode class asserting mem_write while suppressing reg_write
Stimulus: Drive one legal store-word instruction written in assembly, with non-zero, distinct rs1, rs2 and a non-zero offset. Let the outputs settle without clock or reset, then check the complete output tuple against the Stores row.
Support/witness path: None needed. All ten outputs are directly observable on the decoder's own ports.
Public observations: All ten decoder outputs: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, branch_enable, jump, jalr, wb_select, muldiv_op. Expected (0,1,0,1,0x0,0,0,0,0x0,0).
Forbidden: Do not use illegal, reserved or unsupported store funct3 values. Do not enumerate SB, SH and SW as separate cases. Do not add loads, branches, jumps or other classes in this case. Do not test sequences of instructions or clock/reset behavior. Do not rely on internal signals. Do not use instruction-word hex literals; use assembly only.

## Publica — incremento 7

Behavior: A valid word load decodes to the Loads row: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=1, alu_control="0000" (ADD), branch_enable=0, jump=0, jalr=0, wb_select="01" (data-memory read result), muldiv_op=0.
Coverage gap: Loads (opcode 0x03) have no public-port witness. Strategy item 1 requires the Loads row (reg_write=1, alu_src_b_imm=1, ADD, wb_select="01"), and no passing test shows wb_select="01". Existing witnesses are MUL (M tuple), ADD and SUB (OP), ADDI (OP-IMM, including rd=x0), LUI (alu_control only) and SW (Stores). Branches, AUIPC, JAL, JALR, the UNSUPPORTED tuple and combinational transitions are also uncovered. Of these, the load is the simplest next step.
Prerequisites: ADDI already witnesses the immediate-B, ADD and reg_write=1 pattern with wb_select="00". SW already witnesses a memory-class opcode with a non-zero offset. Together they show that the opcode-class controls and the ADD selector are observable.
New factor: Writeback source selection of data-memory read (wb_select="01")
Stimulus: Drive one legal word-load instruction with non-zero rd and rs1 registers that differ from earlier cases, and a non-zero offset. Let the combinational outputs settle. Use no clock or reset.
Support/witness path: None needed. The focal behavior is directly observable on the decoder's output ports.
Public observations: Read all ten outputs: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, branch_enable, jump, jalr, wb_select and muldiv_op. Require every output to be a defined binary value. Compare the full tuple with the Loads row, with wb_select="01" as the focal check.
Forbidden: Do not check unsupported load funct3 values, other load widths, the other classes (branches, AUIPC, JAL, JALR), or transitions between instructions. Do not add clock or reset stimulus or read internal signals. Do not hand-encode the instruction; assemble it only from legal source via assemble_rv32im. Do not use a second case that only changes literals of an existing causal relation.

## Publica — incremento 8

Behavior: A legal AUIPC instruction with non-zero rd and a non-zero upper immediate decodes to the AUIPC row: reg_write=1, mem_write=0, alu_src_a_pc=1, alu_src_b_imm=1, alu_control=ADD, branch_enable=0, jump=0, jalr=0, wb_select=ALU result, muldiv_op=0.
Coverage gap: Strategy items 1 and 7: the AUIPC class (opcode 0x17) has no public-port witness. alu_src_a_pc='1' has never been observed in the suite. LUI is only checked for alu_control, and no jump or branch class has been exercised yet.
Prerequisites: Passing witnesses already exist for driving a single assembled instruction and checking the full output tuple (ADDI, ADD, SUB, SW, LW). The OP-IMM and LUI witnesses already show alu_src_b_imm=1 and the ALU-result writeback selection. The ADD selector alu_control=0000 is already witnessed.
New factor: PC selected as ALU operand A (alu_src_a_pc=1)
Stimulus: Scenario class: one legal AUIPC instruction. Use a non-zero destination register and a non-zero upper immediate, with rd and immediate values distinct from earlier cases. Settle the combinational outputs and read the complete 10-output tuple, rejecting any non-binary value.
Support/witness path: None needed. The focal behavior is directly observable on the decoder's declared output ports.
Public observations: All ten outputs: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, branch_enable, jump, jalr, wb_select and muldiv_op. The expected tuple is (1, 0, 1, 1, ADD, 0, 0, 0, ALU result, 0). The focal assertion is alu_src_a_pc=1 together with jump=0 and branch_enable=0, which distinguishes AUIPC from the PC-selecting JAL class.
Forbidden: Do not combine AUIPC with jump, branch or unsupported-encoding checks. Do not vary funct3 or funct7 fields on the same case. Do not require internal signals, clocks or resets. Do not select reserved or illegal encodings. Do not state binary encodings or instruction words in the plan. Do not repeat an existing causal relation such as ADDI, LW or SW with different literals.

## Publica — incremento 9

Behavior: A valid conditional branch (non-BEQ funct3, e.g. BNE or BLTU) decodes to the Branches row: branch_enable='1', reg_write='0', mem_write='0', alu_src_a_pc='0', alu_src_b_imm='0', jump='0', jalr='0', wb_select="00", muldiv_op='0'. alu_control carries the branch condition code for that funct3 (BNE="0001", BLTU="0100"), not an ALU operation.
Coverage gap: Strategy item 1 (opcode-class controls) and item 6 (branches): no existing witness for the Conditional branches class (opcode 0x63). Nothing yet shows branch_enable='1' or the branch-specific reading of alu_control.
Prerequisites: Passing witnesses already exist for combinational full-tuple observation of a single legal instruction (ADDI, ADD, SUB, SW, LW, AUIPC, LUI, MUL smoke). They also cover the non-writing store class (reg_write=0) and binary-valued outputs. No state, support sequence or other new class is needed.
New factor: Conditional-branch opcode class asserting branch_enable with a branch-specific alu_control
Stimulus: Drive one legal branch instruction built with assemble_rv32im (a branch to a nearby label, with distinct non-zero rs1 and rs2 registers). Choose a funct3 whose branch code is non-zero, such as BNE or BLTU, so the result is distinguishable from the ADD/BEQ default of "0000". Let the combinational outputs settle with no clock or reset, and compare the complete output tuple against the Branches row.
Support/witness path: none: the focal behavior is directly observable on the decoder output ports, so no support sequence is needed
Public observations: All ten decoder outputs: reg_write, mem_write, alu_src_a_pc, alu_src_b_imm, alu_control, branch_enable, jump, jalr, wb_select and muldiv_op. Each must be a defined binary value. The expected tuple is (0, 0, 0, 0, branch code for the chosen funct3, 1, 0, 0, "00", 0).
Forbidden: Do not use hex instruction words or hand-computed encodings. Do not use unsupported branch funct3 values ("010", "011") or any reserved or illegal encoding. Do not sweep all six branch funct3 values. Do not combine this case with jumps, valid/unsupported transitions, or M-extension funct7 variations. Do not access internal signals, and do not use a clock or reset.

## Publica — incremento 9

Behavior: A legal conditional branch instruction (a signed-less-than branch, BLT, with distinct non-zero rs1/rs2 and a non-zero branch offset) decodes to the Branches row. branch_enable='1', alu_control selects the branch condition BLT ("0010"), reg_write='0', mem_write='0', alu_src_a_pc='0', alu_src_b_imm='0', jump='0', jalr='0', wb_select="00" and muldiv_op='0'.
Coverage gap: Conditional branches (opcode 0x63) have no public-port witness. No current test shows branch_enable='1', the branch-specific meaning of alu_control (a non-ADD selector such as BLT/BLTU/BNE), or the branch control tuple with alu_src_b_imm='0' and reg_write='0'. Strategy item 6 is untested, and the existing alu_control witnesses (ADD, SUB, LUI PASS_B) all use the non-branch meaning.
Prerequisites: Combinational drive-and-settle of a full instruction word through the instr port (smoke test and all approved cases); Full-tuple readout with binary-value checking of all ten outputs (SW, LW and AUIPC cases); Opcode-class control decoding for register, immediate, store, load, U-type and PC-operand classes (ADD, SUB, ADDI, SW, LW, LUI, AUIPC); alu_control decoded as a non-zero selector from function fields (SUB, LUI PASS_B)
New factor: Conditional-branch opcode decoding with branch_enable asserted and alu_control carrying the branch-condition meaning
Stimulus: Assemble one legal BLT instruction with distinct non-zero rs1 and rs2 registers and a non-zero forward branch offset, using assemble_rv32im with a label target and a trailing halt loop. Drive that single instruction word on instr and let the outputs settle combinationally. Choose BLT because its selector is non-zero and differs from the ADD default, so a decoder that ignores the branch-condition mapping cannot pass by accident. This is a single-instruction scenario with no sequence, state or prior-instruction dependence.
Support/witness path: none: the focal behavior is directly observable on the decoder's public output ports, so no support sequence is needed
Public observations: branch_enable == 1; alu_control == 0x2 (BLT branch-condition selector); reg_write == 0; mem_write == 0; alu_src_a_pc == 0; alu_src_b_imm == 0; jump == 0; jalr == 0; wb_select == 0x0; muldiv_op == 0; every output is a defined binary value (no U/X/Z)
Forbidden: Do not use JAL or JALR; jump classes combine control with writeback routing and belong to a later case; Do not drive unsupported branch funct3 values (010, 011) or any other illegal or reserved encoding; Do not sweep all six branch funct3 values; one representative branch is enough; Do not mix in M-extension, funct7 neighbour, or unsupported-tuple checks; Do not use clock, reset, internal signals or hierarchy access; Do not use hand-computed instruction words or hex literals; build the stimulus only through assemble_rv32im; Do not count this as new evidence for ADD/SUB/LUI alu_control, load/store, AUIPC or M decoding

