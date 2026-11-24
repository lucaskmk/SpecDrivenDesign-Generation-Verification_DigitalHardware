## Publica — incremento 1

Behavior: ADD returns the low 32 bits of the sum when the mathematical sum exceeds the 32-bit unsigned range.
Coverage gap: ADD modulo-2^32 wraparound
Prerequisites: The ADD selector and nominal result path have a passing public-port witness.
New factor: ADD modulo-2^32 wraparound
Stimulus: Apply ADD to operands whose sum wraps past the 32-bit unsigned range.
Support/witness path: No support sequence is needed; the existing nominal ADD case establishes the selector and result path.
Public observations: Observe result through the declared result port and assert the wrapped sum.
Forbidden: Do not inspect implementation internals.; Do not require comparison-flag assertions for this focal behavior.; Do not add additional operations or edge cases to this case.

## Publica — incremento 2

Behavior: With alu_op selecting SUB, result is operand_a minus operand_b modulo 2^32.
Coverage gap: SUB result behavior for an ordinary subtraction
Prerequisites: none
New factor: SUB result selection
Stimulus: Select SUB with positive operands where operand_a is greater than operand_b, yielding a nonzero difference.
Support/witness path: None; the behavior is directly observable through the declared ports.
Public observations: Check result against the subtraction result.
Forbidden: Do not inspect internal signals or require undeclared ports.; Do not treat comparison flags as newly covered by this case.

## Publica — incremento 3

Behavior: compare_equal is asserted when the two operands are identical.
Coverage gap: The equality comparison output has no public-port witness.
Prerequisites: none
New factor: Equality flag assertion for identical operands.
Stimulus: Apply identical nonzero operands with an already-witnessed selector.
Support/witness path: None required.
Public observations: Observe compare_equal asserted after combinational settling.
Forbidden: Do not inspect internal signals.; Do not count the selector result or other comparison flags as newly covered.

## Publica — incremento 4

Behavior: SUB returns the difference modulo 2^32, including when subtraction borrows.
Coverage gap: SUB borrow/wraparound when the minuend is smaller than the subtrahend
Prerequisites: SUB result behavior is witnessed for ordinary positive operands.
New factor: SUB borrow wraparound
Stimulus: Select subtraction with a smaller unsigned minuend than subtrahend.
Support/witness path: 
Public observations: The result equals the 32-bit modular difference.
Forbidden: Do not require internal signals or hierarchy.; Do not require a clock or reset.; Do not treat comparison flags as newly covered by this case.

