## Publica — incremento 1

Behavior: A supported non-branch operation reports branch_taken as low.
Coverage gap: branch_taken deassertion for a supported non-branch operation
Prerequisites: The suite already has a public witness for a supported OP ADD operation.
New factor: Non-branch branch_taken deassertion
Stimulus: Use a legal ADD source instruction with distinct operands.
Support/witness path: No support sequence is needed; observe branch_taken directly for the ADD scenario.
Public observations: branch_taken is low.
Forbidden: Do not require internal signals or hierarchy access.; Do not count the ADD arithmetic result as newly covered.

## Publica — incremento 2

Behavior: XOR returns the bitwise exclusive-or of the two operands.
Coverage gap: OP-register XOR result
Prerequisites: The existing ADD witness establishes public OP-register result behavior.
New factor: XOR operation selection
Stimulus: Use the OP-register XOR operation with distinct operands.
Support/witness path: None; the XOR result is directly observable through the public result port.
Public observations: result equals the bitwise exclusive-or of the operands.; branch_taken is low.
Forbidden: Do not require internal signals or hierarchy.; Do not use unsupported or malformed instruction encodings.; Do not add clock or reset requirements.

## Publica — incremento 3

Behavior: LUI selection produces result zero and branch_taken zero.
Coverage gap: Unsupported LUI opcode default outputs have no public-port witness.
Prerequisites: none
New factor: LUI opcode default-output behavior
Stimulus: Select the execution-unit inputs corresponding to a legal LUI source instruction, using distinct nonzero operand values.
Support/witness path: 
Public observations: result is zero; branch_taken is zero
Forbidden: Do not inspect implementation internals.; Do not use illegal, reserved, unallocated, or malformed instruction encodings.

## Publica — incremento 4

Behavior: A supported BEQ comparison reports taken for equal operands.
Coverage gap: BEQ taken when the operands are equal
Prerequisites: none
New factor: BEQ taken on equality
Stimulus: A legal BEQ scenario with equal source values.
Support/witness path: None; the focal behavior is directly observable through the declared public ports.
Public observations: branch_taken is asserted.; result is zero for the supported branch.
Forbidden: Do not inspect implementation internals.; Do not add another focal behavior or require exhaustive branch coverage.

