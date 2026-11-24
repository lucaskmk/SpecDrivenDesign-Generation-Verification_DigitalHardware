## Publica — incremento 1

Behavior: An unlisted opcode produces the complete inactive-default output vector.
Coverage gap: Unlisted-opcode inactive-default decoding has no public-port witness.
Prerequisites: none
New factor: Unlisted-opcode default decoding.
Stimulus: Apply a legal FENCE instruction, whose opcode is unlisted by the control-unit behavior table.
Support/witness path: None; the input directly exercises the focal behavior.
Public observations: After combinational propagation, check rd_write, mem_write, load_enable, data_width, load_signed, alu_a_pc, alu_b_imm, wb_sel, branch_enable, jal, and jalr against the inactive defaults.
Forbidden: Do not inspect internal signals or require datapath behavior. Do not use an illegal, reserved, unallocated, or malformed instruction encoding.

## Publica — incremento 2

Behavior: A legal ADDI-class input selects register write and the immediate ALU operand, with all other outputs matching the OP-IMM contract.
Coverage gap: OP-IMM opcode-class control vector
Prerequisites: none
New factor: OP-IMM control-vector decoding
Stimulus: Apply a legal ADDI instruction class with the arithmetic-immediate funct3 value.
Support/witness path: None; the focal behavior is directly observable through the declared inputs and outputs.
Public observations: {'rd_write': '1', 'mem_write': '0', 'load_enable': '0', 'data_width': '10', 'load_signed': '0', 'alu_a_pc': '0', 'alu_b_imm': '1', 'wb_sel': '00', 'branch_enable': '0', 'jal': '0', 'jalr': '0'}
Forbidden: Do not inspect or require implementation internals.; Do not assert datapath behavior.; Do not add other opcode classes or funct3-invariance cases to this case.

## Publica — incremento 3

Behavior: OP selects a register, not an immediate, for the ALU's second operand.
Coverage gap: OP register-register operand-source control: the existing OP witness checks only rd_write, not that alu_b_imm is deasserted.
Prerequisites: The existing OP smoke test witnesses the OP class and rd_write.; The existing ADDI case witnesses alu_b_imm asserted for an immediate-operand class.
New factor: Register-register second-operand selection for OP.
Stimulus: Use a legal register-register ADD instruction and observe the OP control output for the ALU's second-operand source.
Support/witness path: No support sequence is needed; the existing ADDI case provides the contrasting immediate-operand public witness.
Public observations: For the OP instruction, alu_b_imm is deasserted.
Forbidden: Do not inspect internal signals or require datapath behavior.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.; Do not assert unrelated outputs as additional coverage for this case.

## Publica — incremento 4

Behavior: A supported branch encoding asserts branch_enable.
Coverage gap: Valid branch decoding has no public-port witness.
Prerequisites: none
New factor: Branch enable for a valid branch encoding.
Stimulus: Use a legal BEQ instruction source and observe the control-unit outputs.
Support/witness path: 
Public observations: branch_enable is asserted.
Forbidden: Do not infer branch-taken behavior; it is not an output of control_unit.; Do not use reserved or malformed instruction encodings.; Do not access implementation internals.

