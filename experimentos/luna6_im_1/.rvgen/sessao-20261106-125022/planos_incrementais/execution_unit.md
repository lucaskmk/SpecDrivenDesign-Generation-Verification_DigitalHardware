## Publica — incremento 1

Behavior: For the legal OP SUB operation, result equals operand_a minus operand_b modulo 2^32.
Coverage gap: OP subtraction (SUB) result semantics
Prerequisites: The passing OP ADD witness establishes a basic public result path for the OP opcode.
New factor: Subtraction semantics
Stimulus: Exercise legal OP subtraction with unequal nonzero operands whose difference does not wrap.
Support/witness path: No support sequence is needed; subtraction is directly observable on the public result port.
Public observations: result equals operand_a minus operand_b.; branch_taken is false.
Forbidden: Do not require internal signals or state.; Do not add another operation or a wraparound edge case to this scenario.; Do not use an illegal or reserved instruction encoding.

## Publica — incremento 2

Behavior: Compute the bitwise XOR of operand_a and operand_b.
Coverage gap: OP register-register XOR
Prerequisites: OP register-register selection is already witnessed by passing ADD and SUB cases.
New factor: XOR operation
Stimulus: Use a legal register-register XOR scenario with distinct, nonzero operands chosen to make the XOR result distinguishable.
Support/witness path: No support sequence is needed; the operation is directly observable through the public inputs and result output.
Public observations: After combinational propagation settles, result equals the bitwise XOR of the two operands.
Forbidden: Do not require implementation internals.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.

## Publica — incremento 3

Behavior: OP OR returns the bitwise OR of operand_a and operand_b.
Coverage gap: OP bitwise OR result
Prerequisites: The suite already has public result witnesses for OP arithmetic and bitwise logic.
New factor: OP bitwise OR
Stimulus: Use a legal register-register OR instruction with unequal operands whose overlapping and non-overlapping set bits distinguish OR from XOR and AND.
Support/witness path: None required.
Public observations: After combinational settling, result equals the bitwise OR of the two operands.
Forbidden: Do not inspect implementation internals.; Do not add unsupported or malformed instruction encodings.

## Publica — incremento 4

Behavior: For the supported OP AND selector, result is the bitwise intersection of operand_a and operand_b.
Coverage gap: OP register-register bitwise AND
Prerequisites: Existing public-port OP ADD, SUB, XOR, and OR cases demonstrate combinational OP result behavior.
New factor: OP bitwise AND
Stimulus: A legal register-register AND with nonzero operands whose intersection is distinguishable from either operand.
Support/witness path: None; the focal result is directly observable through the public result port.
Public observations: result equals the bitwise AND of the supplied operands.
Forbidden: Do not inspect implementation internals.; Do not require assertions about behavior unrelated to the focal AND result.; Do not use an illegal or malformed instruction encoding.

