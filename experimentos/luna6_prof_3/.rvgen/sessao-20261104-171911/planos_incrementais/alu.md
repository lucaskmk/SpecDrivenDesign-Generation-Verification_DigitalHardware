## Publica — incremento 1

Behavior: SUB produces operand_a minus operand_b modulo 2^32.
Coverage gap: SUB operation result has no public-port witness.
Prerequisites: The passing ADD smoke test establishes a public-port witness for a basic arithmetic operation.; No support sequence is required.
New factor: SUB operation result
Stimulus: Apply SUB to the same nominal operand pair used by the passing ADD smoke test, changing only the operation selector.
Support/witness path: 
Public observations: Check that result equals operand_a minus operand_b modulo 2^32.
Forbidden: Do not inspect or require internal signals or hierarchy.; Do not claim comparison flags, other operation selectors, or arithmetic boundaries as newly covered.

## Publica — incremento 2

Behavior: An ADD whose mathematical sum crosses the 32-bit unsigned boundary produces the low 32 bits of the sum.
Coverage gap: ADD modulo-2^32 wraparound
Prerequisites: Passing evidence that the ADD selector produces an arithmetic result.
New factor: ADD wraparound
Stimulus: Select ADD for operands whose sum crosses the 32-bit unsigned boundary.
Support/witness path: 
Public observations: Observe result through the public result port and require the modulo-2^32 sum.
Forbidden: Do not inspect implementation internals.; Do not claim comparison flags or other operation selectors as covered by this case.

## Publica — incremento 3

Behavior: The public equal output reflects bit-for-bit equality of the current operands.
Coverage gap: Equality flag: bitwise-equal operands must assert equal, and a one-bit difference must deassert it.
Prerequisites: none
New factor: Equality-flag behavior
Stimulus: Use a pair of equal operands and a pair differing by one bit, with the selector and the unchanged operand held fixed.
Support/witness path: 
Public observations: equal is 1 for the equal pair.; equal is 0 for the one-bit-different pair.
Forbidden: Do not inspect or require implementation internals.; Do not assert unrelated result or comparison behavior.

## Publica — incremento 4

Behavior: The AND selector produces the bitwise intersection of operand_a and operand_b on result.
Coverage gap: AND operation result: bitwise AND of the two operands
Prerequisites: None; the public operands and result are sufficient to observe this combinational behavior.
New factor: AND result
Stimulus: Apply two distinct, mixed-bit operands with an AND operation selected.
Support/witness path: None required.
Public observations: Check that result equals the bitwise AND of the driven operands.
Forbidden: Do not inspect internal signals or require other operation results, comparison flags, reserved selectors, or additional cases.

