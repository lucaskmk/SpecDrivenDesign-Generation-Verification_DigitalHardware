## Publica — incremento 1

Behavior: For valid OP SUB selectors, result is operand_a minus operand_b modulo 2^32.
Coverage gap: SUB operation selection and subtraction result
Prerequisites: The public combinational result is already witnessed by the ADD case; no state or support sequence is required.
New factor: Subtraction
Stimulus: A legal SUB operation with distinct nontrivial operands chosen so the difference is nonzero.
Support/witness path: None; the SUB result is directly observable at the public result port.
Public observations: After combinational settling, result equals the 32-bit modular difference of operand_a and operand_b.
Forbidden: Do not inspect internals, require unsupported encodings, or assert behavior beyond the SUB result.

## Publica — incremento 2

Behavior: For OP with the XOR selector, result is the bitwise XOR of the two operands.
Coverage gap: OP XOR result
Prerequisites: Public-port witnesses already cover OP ADD and SUB.; The existing nontrivial operand pair can be reused to distinguish the XOR result.
New factor: XOR operation selection
Stimulus: Use the existing nontrivial operand pair with the OP opcode and XOR function selector.
Support/witness path: None; the result directly witnesses the focal behavior.
Public observations: The public result port equals the bitwise XOR of operand_a and operand_b.
Forbidden: Do not inspect implementation internals.; Do not add another arithmetic, logic, or edge-case behavior to this case.

## Publica — incremento 3

Behavior: OP OR returns the bitwise OR of its operands.
Coverage gap: OP OR has no public-port result witness.
Prerequisites: none
New factor: OR operation selection
Stimulus: Select the legal OP OR encoding and use operands whose AND, OR, and XOR results are pairwise distinguishable.
Support/witness path: None; the result is directly observable on the public result port.
Public observations: After combinational settling, result equals the operands' bitwise OR.
Forbidden: Do not inspect hierarchy or require implementation internals.; Do not claim coverage of other logic operations, OP-IMM operations, invalid encodings, or operand-dependence edges from this case.

## Publica — incremento 4

Behavior: The OP AND selection returns the bitwise intersection of its two operands.
Coverage gap: OP bitwise AND has no passing public-port witness.
Prerequisites: Combinational selector driving and result observation already have passing witnesses for OP ADD, XOR, and OR.
New factor: OP bitwise AND
Stimulus: Use the legal OP AND operation with operands whose bitwise intersection is distinguishable from their bitwise union and exclusive-or.
Support/witness path: 
Public observations: Observe result and require it to equal the bitwise intersection of operand_a and operand_b.
Forbidden: Do not inspect internal signals or claim coverage of other operations or edge cases.

