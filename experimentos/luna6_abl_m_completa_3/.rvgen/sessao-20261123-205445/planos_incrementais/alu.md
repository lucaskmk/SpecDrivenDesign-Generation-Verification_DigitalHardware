## Publica — incremento 1

Behavior: AND returns the bitwise conjunction of its operands.
Coverage gap: Register-register AND behavior has no public-port witness.
Prerequisites: The passing ADD case witnesses driving the ALU inputs and observing both outputs.
New factor: Register-register AND behavior.
Stimulus: Select the legal register-register AND operation and use operands with both shared set bits and set bits present in only one operand.
Support/witness path: None required; the existing ADD witness establishes the public input/output path.
Public observations: The result equals the bitwise conjunction of the operands.; branch_taken is false.
Forbidden: Do not require or inspect implementation internals.; Do not add unrelated operation or edge-case checks to this case.

## Publica — incremento 2

Behavior: For the OR selector, result is the bitwise OR of the two operands and branch_taken is false.
Coverage gap: Register-register OR (OR)
Prerequisites: Register-register operation behavior has a passing public-port witness.; Non-branch behavior has a passing public-port witness.
New factor: OR operation selection
Stimulus: Use a legal register-register OR source instruction with operands whose bitwise OR differs from their bitwise AND.
Support/witness path: None required.
Public observations: result equals the bitwise OR of operand_a and operand_b.; branch_taken is false.
Forbidden: Do not require internal signals or hierarchy.; Do not add a clock or reset stimulus.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.

## Publica — incremento 3

Behavior: XOR returns the bitwise exclusive-OR of the current operands.
Coverage gap: The register-register XOR operation has no public-port witness. The current suite witnesses ADD, AND, and OR, with branch_taken low for those non-branch operations.
Prerequisites: The existing cases witness the register-register opcode class and direct combinational observation of result.; The existing cases witness branch_taken low for non-branch operations.
New factor: Register-register XOR result semantics.
Stimulus: Use legal register-register XOR assembly source with operands whose bit patterns distinguish exclusive-OR from both AND and OR.
Support/witness path: None; the focal result is directly observable through the public result port.
Public observations: result equals the bitwise exclusive-OR of the driven operands.; branch_taken is low.
Forbidden: Do not require internal signals or hierarchy.; Do not use unsupported, reserved, illegal, or malformed instruction encodings.; Do not add another operation or an edge-case claim to this case.

## Publica — incremento 4

Behavior: For a legal R-type SUB selector, result is operand_a minus operand_b modulo 2^32.
Coverage gap: R-type SUB result is not yet covered; the passing ADD witness does not establish subtraction.
Prerequisites: R-type operation selection and combinational result are witnessed by the passing ADD case.
New factor: R-type subtraction
Stimulus: A legal register-register SUB with unequal operands and a nonzero difference.
Support/witness path: None; drive the public ALU inputs directly.
Public observations: result equals the subtraction result.; branch_taken is false.
Forbidden: Do not require implementation internals.; Do not treat wraparound as covered by this nominal subtraction case.

