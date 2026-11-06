## Publica — incremento 6

Behavior: A legal register-register SLL instruction selects alu_control 0x2.
Coverage gap: Valid base OP SLL encoding selects the SLL ALU control.
Prerequisites: The existing ADD case witnesses valid base OP register-operand controls.
New factor: SLL ALU selector decoding
Stimulus: Use a legal register-register SLL instruction with nonzero destination and source registers.
Support/witness path: No support sequence is needed; the existing ADD register-decode witness establishes the base OP context.
Public observations: {'alu_control': '0x2'}
Forbidden: Do not inspect implementation internals.; Do not require a clock or reset.; Do not assert unrelated controls for this focal behavior.

## Publica — incremento 7

Behavior: A valid register-register XOR selects the XOR ALU operation.
Coverage gap: Base OP XOR encoding and its ALU selector have no public-port witness.
Prerequisites: Valid base OP decode is witnessed by ADD.; Base OP function-dependent ALU selection is witnessed by ADD, SUB, and SLL.
New factor: XOR operation selection
Stimulus: A valid register-register XOR instruction with ordinary nonzero source and destination registers.
Support/witness path: None required.
Public observations: After the instruction input settles, observe alu_control selecting XOR and the register-register OP control tuple: reg_write asserted, both operand selectors choosing registers, and other class controls deasserted.
Forbidden: Do not require internal signals.; Do not use an unsupported or malformed instruction encoding.; Do not claim coverage of other OP operations or unrelated instruction classes.

## Publica — incremento 8

Behavior: A valid store asserts mem_write.
Coverage gap: A valid store instruction asserting mem_write
Prerequisites: The suite already demonstrates combinational instruction decoding.; The suite already demonstrates immediate-operand selection with ADDI.
New factor: Store write enable
Stimulus: A legal RV32IM SW instruction using ordinary nonzero source and base registers.
Support/witness path: None required.
Public observations: mem_write is asserted.
Forbidden: Do not inspect implementation internals.; Do not use unsupported or malformed instruction encodings.; Do not assert unrelated outputs as additional coverage claims.

## Publica — incremento 9

Behavior: A valid load selects memory-read data for writeback.
Coverage gap: Valid load instructions select the data-memory read result for writeback.
Prerequisites: none
New factor: Memory-read writeback selection.
Stimulus: A legal word-load instruction with a nonzero destination and base register.
Support/witness path: None; the focal behavior is directly observable at the public wb_select port.
Public observations: wb_select is 0x1.
Forbidden: Do not inspect internal signals.; Do not use an illegal or unsupported instruction encoding.

