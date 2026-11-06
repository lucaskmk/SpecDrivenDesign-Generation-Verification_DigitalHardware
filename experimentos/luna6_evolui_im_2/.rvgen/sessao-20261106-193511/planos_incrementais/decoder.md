## Publica — incremento 6

Behavior: Selects SLL with alu_control 0010 while retaining the OP control tuple.
Coverage gap: RV32I OP SLL encoding: funct3 001 with funct7 0000000.
Prerequisites: The OP class and its register-write and operand-source controls have passing public-port witnesses.
New factor: OP SLL operation selection
Stimulus: Use a legal SLL instruction with a nonzero destination and register operands.
Support/witness path: None required; the instruction directly exercises the focal behavior.
Public observations: Check alu_control selects SLL.; Check the complete output tuple matches the OP class, including register write enabled, both operand selectors low, and wb_select selecting the ALU result.
Forbidden: Do not require internal signals.; Do not use an illegal or reserved instruction encoding.

## Publica — incremento 7

Behavior: A legal OP XOR instruction selects the XOR ALU operation while retaining the OP control tuple.
Coverage gap: OP XOR function encoding is not yet witnessed.
Prerequisites: A public full-tuple witness for OP ADD establishes the OP class controls.
New factor: XOR operation selection
Stimulus: One legal register-register XOR instruction using the standard OP function encoding.
Support/witness path: No support sequence is needed; the XOR instruction itself is the public witness.
Public observations: {'reg_write': '1', 'mem_write': '0', 'alu_src_a_pc': '0', 'alu_src_b_imm': '0', 'alu_control': '0101', 'branch_enable': '0', 'jump': '0', 'jalr': '0', 'wb_select': '00'}
Forbidden: Do not inspect implementation internals.; Do not require arithmetic-result computation or exhaustive OP coverage.

## Publica — incremento 8

Behavior: For AUIPC, alu_src_a_pc is asserted.
Coverage gap: AUIPC selection of the PC as ALU operand A has no public-port witness.
Prerequisites: No support sequence is needed; the decoder is combinational.; Existing public witnesses cover ADD, SUB, SLL, and XOR OP controls, ADDI controls, and LUI's PASS_B selector. The ADDI-with-x0 case witnesses reg_write remaining asserted for rd=x0.
New factor: AUIPC selects the PC as ALU operand A.
Stimulus: Present a legal AUIPC instruction using representative nonzero register and immediate fields.
Support/witness path: None.
Public observations: After the instruction settles, observe alu_src_a_pc='1'.
Forbidden: Do not inspect decoder internals.; Do not use a clock or reset.; Do not assert unrelated controls as newly covered behavior.; Do not use an illegal or malformed instruction encoding.

## Publica — incremento 9

Behavior: A legal register-register SLT instruction is recognized as an OP instruction and selects the signed-less-than ALU operation.
Coverage gap: RV32I OP signed less-than (SLT) function decoding
Prerequisites: Existing ADD, SUB, SLL, and XOR cases witness valid OP register-write and register-register operand controls.
New factor: SLT selects the signed-less-than ALU operation.
Stimulus: A legal register-register signed less-than instruction.
Support/witness path: None required; the instruction directly exposes the focal behavior through the decoder outputs.
Public observations: Check the complete public output tuple: register write asserted; memory write, PC operand selection, immediate operand selection, branch, jump, and JALR controls deasserted; ALU control selects signed less-than; writeback selects the ALU result.
Forbidden: Do not inspect implementation internals.; Do not use an illegal or unsupported instruction encoding.; Do not add another OP operation or vary unrelated instruction fields as additional coverage.

