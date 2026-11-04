## Publica — incremento 1

Behavior: The decoder asserts reg_write for a valid ADDI even when its destination is x0.
Coverage gap: A valid register-writing instruction with rd=x0 must still assert reg_write.
Prerequisites: The passing ADDI case establishes the ordinary OP-IMM ADD controls. No additional support sequence is needed.
New factor: rd=x0
Stimulus: A legal ADDI with x0 as its destination.
Support/witness path: None; observe the decoder outputs directly for this instruction.
Public observations: reg_write is asserted.
Forbidden: Do not require internal signals or assert that the decoder suppresses reg_write for x0.

## Publica — incremento 2

Behavior: For a legal LUI instruction, alu_control is PASS_B (0xA).
Coverage gap: LUI selects PASS_B on alu_control.
Prerequisites: none
New factor: LUI selects PASS_B.
Stimulus: A legal LUI instruction with a nonzero destination and an upper immediate.
Support/witness path: Direct public-port witness: drive the LUI instruction on instr and observe alu_control; no support sequence is needed.
Public observations: alu_control equals 0xA.
Forbidden: Do not inspect hierarchy or require internal signals.; Do not use unsupported or malformed instruction encodings.; Do not make this case evidence for unrelated LUI controls or other instruction classes.

## Publica — incremento 3

Behavior: A valid OP ADD selects register operands, asserts reg_write, and selects ALU ADD.
Coverage gap: Valid OP register-register instruction decoding, represented by ADD
Prerequisites: none
New factor: OP selects rs2 as ALU operand B.
Stimulus: A legal register-register ADD instruction with nonzero destination and source registers.
Support/witness path: 
Public observations: Check the complete output tuple through declared ports.; Confirm reg_write is asserted, alu_src_b_imm is deasserted, alu_control selects ADD, and the remaining controls match the OP class.
Forbidden: Do not inspect hierarchy or require internal signals.; Do not use illegal or unsupported instruction encodings.

## Publica — incremento 4

Behavior: A valid register-register SUB instruction asserts reg_write, selects register operands, and sets alu_control to the SUB selector.
Coverage gap: OP SUB encoding: funct3 000 with the required SUB funct7 selects SUB.
Prerequisites: The existing passing OP ADD case witnesses the OP control tuple and register-operand selection.
New factor: SUB function decoding
Stimulus: A legal register-register SUB scenario, matched to the existing ADD case in its other instruction fields so the changed function encoding is the sole new semantic factor.
Support/witness path: None required; the focal behavior is directly observable from the decoder's public outputs.
Public observations: Check the complete output tuple: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=0, alu_control=SUB, branch_enable=0, jump=0, jalr=0, and wb_select=00.
Forbidden: Do not inspect implementation internals.; Do not add another OP operation or unsupported-encoding case to this incremental case.

