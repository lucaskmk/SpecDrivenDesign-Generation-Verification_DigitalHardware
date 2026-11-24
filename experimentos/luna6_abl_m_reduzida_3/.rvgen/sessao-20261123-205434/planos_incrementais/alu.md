## Publica — incremento 1

Behavior: The ALU selects subtraction for the legal SUB selector and returns operand_a minus operand_b, with branch_taken low.
Coverage gap: Register-register SUB has no public-port witness; the passing suite covers only ADD.
Prerequisites: The existing ADD test establishes a public witness for register-register arithmetic and the shared opcode.
New factor: Subtraction result selection
Stimulus: A legal register-register SUB scenario with distinct operands chosen so the subtraction result is nonzero and does not wrap.
Support/witness path: None; the SUB result and branch_taken are directly observable through the public ports.
Public observations: result equals the specified subtraction result.; branch_taken is low.
Forbidden: Do not inspect implementation internals.; Do not use illegal or unsupported instruction encodings.; Do not treat the existing ADD relation with different literals as new evidence.

## Publica — incremento 2

Behavior: The result is the bitwise XOR of operand_a and operand_b.
Coverage gap: Register-register XOR (OP with funct3 0x4 and funct7 0x00) has no public-port witness.
Prerequisites: none
New factor: Bitwise XOR result.
Stimulus: Use legal RV32IM source selecting register-register XOR, with distinct operands whose set bits make the XOR result distinguishable.
Support/witness path: 
Public observations: Assert result equals operand_a XOR operand_b.; Assert branch_taken is low.
Forbidden: Do not inspect implementation internals.; Do not add assertions for unrelated operations or claim exhaustive coverage.

## Publica — incremento 3

Behavior: The result is the bitwise AND of operand_a and operand_b.
Coverage gap: Register-register AND (OP, funct3 0x7, funct7 0x00) has no public-port witness.
Prerequisites: None; both operands can be driven directly through declared inputs.
New factor: Register-register bitwise AND result semantics.
Stimulus: Use legal RV32IM source for a register-register AND with distinct operand patterns that make the intersection observable.
Support/witness path: None; observe the result directly.
Public observations: Assert result equals the operands' bitwise intersection and branch_taken is low.
Forbidden: Do not require internals, unsupported encodings, or coverage of any additional operation in this case.

## Publica — incremento 4

Behavior: For a legal register-register OR instruction, result is the bitwise inclusive OR of operand_a and operand_b.
Coverage gap: OP OR result
Prerequisites: Passing ADD, SUB, XOR, and AND cases establish the public instruction-input and combinational-result path.; Passing XOR and AND cases establish register-register logical-operation stimulus and non-branch output observation.
New factor: OR operation selection and result
Stimulus: Use a legal register-register OR instruction with distinct operands whose set bits make the inclusive-OR result observable.
Support/witness path: None required.
Public observations: result equals the bitwise inclusive OR of the supplied operands.; branch_taken is low.
Forbidden: Do not inspect or require implementation internals.; Do not add unsupported or malformed instruction encodings.; Do not claim coverage of other unwitnessed operations or edge cases.

