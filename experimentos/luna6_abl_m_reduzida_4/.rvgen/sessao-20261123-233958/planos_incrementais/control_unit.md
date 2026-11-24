## Publica — incremento 1

Behavior: A valid LUI instruction selects PASS_B.
Coverage gap: LUI selects PASS_B as its ALU operation
Prerequisites: The passing suite already drives a valid LUI instruction.
New factor: LUI selects PASS_B as its ALU operation
Stimulus: A legal LUI instruction using the established register and immediate-field pattern.
Support/witness path: None required.
Public observations: Assert that alu_op selects PASS_B.
Forbidden: Do not require internal signals.; Do not use an unsupported or malformed instruction.

## Publica — incremento 2

Behavior: A valid LUI selects the U-type immediate format.
Coverage gap: LUI U-type immediate selection
Prerequisites: A valid LUI already has public-port witnesses for reg_write and PASS_B selection. No additional prerequisite is needed.
New factor: U-type immediate selection
Stimulus: A legal LUI instruction with a nonzero destination register and a nonzero U-type immediate.
Support/witness path: No support sequence is required; the instruction itself is the public witness. Do not count its already-witnessed register-write or PASS_B behavior as newly covered.
Public observations: Assert only that imm_sel selects the U-type format ("100").
Forbidden: Do not inspect implementation internals or require assertions about other outputs.

## Publica — incremento 3

Behavior: For a valid AUIPC instruction, alu_src_a_pc is asserted.
Coverage gap: AUIPC selects the current PC as ALU operand A.
Prerequisites: Passing LUI witnesses establish the U-type instruction context.; A legal AUIPC source instruction can directly expose alu_src_a_pc.
New factor: AUIPC selects PC as ALU operand A.
Stimulus: A legal AUIPC instruction with a nonzero destination register and a distinguishable U-type immediate.
Support/witness path: None; the focal behavior is directly observable on alu_src_a_pc.
Public observations: Assert alu_src_a_pc is asserted.
Forbidden: Do not inspect internal signals.; Do not assert unrelated outputs as additional focal behaviors.; Do not use malformed or reserved instruction encodings.

## Publica — incremento 4

Behavior: For LUI, alu_src_b_imm is asserted.
Coverage gap: LUI selection of an immediate for ALU operand B
Prerequisites: none
New factor: LUI selects the immediate for ALU operand B.
Stimulus: A legal LUI instruction with a nonzero U-type immediate.
Support/witness path: 
Public observations: alu_src_b_imm is asserted.
Forbidden: Do not require implementation internals.; Do not treat the already witnessed LUI controls as new coverage.; Do not assert unrelated output behavior as part of this case.

