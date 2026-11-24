## Publica — incremento 1

Behavior: XORI returns the bitwise XOR of its operands.
Coverage gap: OP-IMM XORI has no public-port witness.
Prerequisites: None beyond the declared combinational public interface; the suite already witnesses OP-IMM decode and combinational result observation.
New factor: XORI behavior
Stimulus: Apply the legal OP-IMM XOR operation using the same operands as the passing ADDI witness.
Support/witness path: None required.
Public observations: After combinational settling, result equals the bitwise XOR of the driven operands.
Forbidden: Do not inspect internals, require a clock, or use unsupported or malformed instruction encodings.

## Publica — incremento 2

Behavior: ORI returns the bitwise OR of operand_a and operand_b.
Coverage gap: OP-IMM ORI operation
Prerequisites: OP-IMM behavior has public-port witnesses through ADDI and XORI.; Combinational result observation has a public-port witness.
New factor: OP-IMM ORI bitwise-OR behavior
Stimulus: Use a legal ORI source instruction and operands whose set bits overlap in at least one position and differ in another, making OR distinguishable from XOR.
Support/witness path: None; drive the ALU public inputs directly.
Public observations: After combinational settling, result equals the bitwise OR of the two operands.
Forbidden: Do not inspect implementation internals.; Do not require a clock or reset.; Do not claim coverage for other operations or edge cases.

## Publica — incremento 3

Behavior: ANDI returns the bitwise AND of operand_a and operand_b.
Coverage gap: OP-IMM ANDI behavior has no public-port witness.
Prerequisites: OP-IMM decoding and combinational result observation are witnessed by ADDI, XORI, and ORI.
New factor: ANDI operation selection
Stimulus: Use a legal ANDI source instruction with operands chosen so their bitwise intersection is distinguishable from either operand and from their bitwise union.
Support/witness path: None; drive the public inputs directly.
Public observations: After combinational settling, result equals the bitwise AND of the two operands.
Forbidden: Do not inspect implementation internals.; Do not use an illegal or reserved instruction encoding.; Do not add another operation or edge case to this scenario.

## Publica — incremento 4

Behavior: For a legal SUB instruction, result equals operand_a minus operand_b modulo 32 bits.
Coverage gap: OP subtraction (SUB): no public-port witness for the defined R-type subtraction operation.
Prerequisites: None; the ALU is combinational, and the operation can be directly observed through the declared ports.
New factor: Subtraction
Stimulus: Use a legal SUB source instruction with unequal operands whose order affects the result.
Support/witness path: None required; result directly witnesses the focal behavior.
Public observations: The result equals operand_a minus operand_b modulo 32 bits.
Forbidden: Do not use reserved, illegal, unallocated, or malformed instruction encodings.; Do not inspect or require implementation internals.

