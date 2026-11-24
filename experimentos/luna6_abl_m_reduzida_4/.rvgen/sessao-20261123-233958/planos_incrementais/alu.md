## Publica — incremento 1

Behavior: SUB computes operand_a minus operand_b modulo 2^32.
Coverage gap: SUB has no public-port result witness.
Prerequisites: The existing ADD case establishes public input driving, operation selection, and result observation.
New factor: SUB operation selection and result.
Stimulus: Use a nominal subtraction case with the same operand relationship as the existing ADD witness. Check the operation result and, as required by the test strategy, all three operand-defined flags.
Support/witness path: None required.
Public observations: Observe result through the declared result port.; Check equal, signed_less, and unsigned_less through their declared ports for the driven operands.
Forbidden: Do not access implementation internals or require hierarchy.; Do not treat this case as evidence for other ALU operations, edge cases, or complete flag coverage.

## Publica — incremento 2

Behavior: An ADD whose unsigned sum exceeds 32 bits returns the low 32 bits.
Coverage gap: ADD modulo-2^32 wraparound
Prerequisites: The passing ADD smoke test witnesses ordinary addition; the approved SUB case witnesses subtraction wraparound and checks all three flags.
New factor: ADD overflow wraparound
Stimulus: Select ADD with operands whose unsigned sum exceeds the 32-bit range. Check the wrapped result and all three flags after combinational settling.
Support/witness path: None; the ADD result is directly observable through the public result port.
Public observations: Check result against the low 32 bits of the sum, and check equal, signed_less, and unsigned_less against the driven operands.
Forbidden: Do not inspect internals, add state or clock requirements, or claim this case covers other arithmetic edges or comparison classes.

## Publica — incremento 3

Behavior: XOR returns the bitwise exclusive OR of the current operands.
Coverage gap: XOR operation result has no public-port witness.
Prerequisites: none
New factor: XOR result behavior
Stimulus: Use a binary operand pair with differing bit patterns and select XOR.
Support/witness path: 
Public observations: After combinational settling, check that result is the bitwise exclusive OR of the driven operands.
Forbidden: Do not inspect internal signals.; Do not add assertions for unrelated behaviors.; Do not use reserved selectors or malformed instruction encodings.

## Publica — incremento 4

Behavior: The OR selector produces the bitwise OR of the current operands.
Coverage gap: OR operation: bitwise OR result for selector 01000
Prerequisites: Public combinational settling is witnessed by the ADD, SUB, and XOR cases.; A bitwise-operation result is witnessed by the XOR case.
New factor: OR operation
Stimulus: Select OR with two nontrivial operands that have both overlapping and non-overlapping set bits.
Support/witness path: None; drive the operands and selector directly.
Public observations: After combinational settling, result equals the bitwise OR of the driven operands.
Forbidden: Do not require implementation internals.; Do not enumerate operand combinations.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.

