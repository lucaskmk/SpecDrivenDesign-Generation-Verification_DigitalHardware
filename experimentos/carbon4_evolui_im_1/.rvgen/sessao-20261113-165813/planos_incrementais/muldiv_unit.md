## Publica — incremento 1

Behavior: Combinational selection of MUL, MULH, MULHSU, MULHU, DIV, DIVU, REM, and REMU via muldiv_op so that each operation code routes its distinct nominal 32-bit arithmetic result to result
Coverage gap: Operation selector decoding across all eight RV32M muldiv_op modes
Prerequisites: Baseline combinational evaluation of nominal low-word multiplication on public ports
New factor: Selection among all eight muldiv_op operation codes
Stimulus: Hold non-trivial non-zero operand pairs with negative signed interpretation fixed on operand_a and operand_b while varying only muldiv_op across all eight defined RV32M operation modes using non-aliasing magnitudes where low-word product, signed high-word product, mixed-sign high-word product, unsigned high-word product, signed quotient, unsigned quotient, signed remainder, and unsigned remainder produce mutually distinct results without triggering zero-divisor or signed-overflow overrides
Support/witness path: Direct combinational observation on result from public inputs operand_a, operand_b, and muldiv_op with no state-setup support sequence required
Public observations: Mutually distinct expected words on result as muldiv_op selects each of the four multiplication slice/signedness modes on a fixed negative-MSB operand pair; Mutually distinct expected words on result as muldiv_op selects signed quotient, unsigned quotient, signed remainder, and unsigned remainder on a fixed non-divisible negative-MSB dividend and positive divisor pair
Forbidden: Inspecting internal signals or sub-expressions inside muldiv_unit; Combining division-by-zero or minimum-signed-integer overflow inputs into nominal selector-decoding checks; Enumerating Cartesian combinations of operands across selectors

## Publica — incremento 2

Behavior: MULHSU treats operand_a as signed two's-complement and operand_b as unsigned binary so swapping opposite-sign operands changes the upper 32-bit product word, whereas MUL, MULH, and MULHU remain commutative across all four operand sign quadrants including the minimum negative signed boundary.
Coverage gap: Multiplication signedness and operand-order isolation (Test strategy item 2)
Prerequisites: Combinational muldiv_op decoding across MUL, MULH, MULHSU, and MULHU, already witnessed on public ports in test_muldiv_unit_selector_decoding_all_ops.
New factor: Asymmetric operand signedness under operand swap in upper-word multiplication
Stimulus: Combinational multiplication scenario class driving non-trivial positive and negative-MSB 32-bit magnitudes across all four operand sign quadrants on operand_a and operand_b, including swapped opposite-sign operand pairs and the minimum negative signed boundary pair, under the multiplication operation selectors.
Support/witness path: Support relies only on already-verified multiplication selector selection on muldiv_op; the focal behavior is directly witnessed on the combinational result port across sign-quadrant and operand-swap input combinations.
Public observations: On port result, MULHSU produces distinct upper-word values when a negative-MSB operand and a positive operand are swapped between operand_a and operand_b (matching signed operand_a times unsigned operand_b in each orientation), while MUL, MULH, and MULHU produce identical outputs under operand swap; across all four sign quadrants and at the minimum negative signed boundary pair, result matches exact 64-bit product slice semantics for MUL, MULH, MULHSU, and MULHU.
Forbidden: Do not access internal signals or module hierarchy; do not reference non-existent clock or reset ports; do not introduce division, remainder, zero-divisor, or signed-division-overflow scenarios in this case.

## Publica — incremento 3

Behavior: When operand_b is zero, DIV and DIVU produce the all-ones word, REM and REMU return operand_a unchanged, and MUL, MULH, MULHSU, and MULHU produce zero without raising any runtime divide-by-zero error in active or unselected combinational paths.
Coverage gap: Division-by-zero boundary handling across all muldiv_op selectors (Strategy 4)
Prerequisites: Combinational muldiv_op selector decoding across all eight RV32M operations on non-zero operands
New factor: Zero second operand triggering the division-by-zero boundary
Stimulus: Combinational scenario class holding the second operand at zero while applying representative first-operand classes (non-zero positive, non-zero negative distinct from all-ones so remainder passthrough cannot alias the division quotient, minimum signed negative, and zero) across the full set of defined operation selector values.
Support/witness path: Direct combinational drive on public inputs operand_a, operand_b, and muldiv_op with immediate combinational observation on public output result; no sequential support sequence is required because the entity is stateless.
Public observations: For every tested operand_a with operand_b equal to zero, result equals zero across all four multiplication selectors; For every tested operand_a with operand_b equal to zero, result equals the all-ones word for both signed and unsigned division selectors; For every tested operand_a with operand_b equal to zero, result equals operand_a for both signed and unsigned remainder selectors and differs from the division result whenever operand_a is not all-ones
Forbidden: Reading or asserting internal DUT signals or hierarchy; Combining signed-overflow stimulus or non-zero divisor sweeps into this test case; Exhaustive enumeration of operand_a values

## Publica — incremento 4

Behavior: Combinational signed division overflow handling on the minimum negative 32-bit signed dividend and negative-one divisor pair, returning the minimum negative 32-bit signed integer for signed quotient and zero for signed remainder without runtime error while leaving unsigned division, unsigned remainder, multiplication operations, and single-factor neighbor pairs unaffected
Coverage gap: Signed division overflow edge case when the dividend is the minimum negative 32-bit signed integer and the divisor is negative one
Prerequisites: Combinational muldiv_op selector decoding across all eight RV32M operations; Signed, mixed-sign, and unsigned 64-bit multiplication slice selection; Division-by-zero boundary handling across all operation selectors
New factor: Signed division overflow substitution at minimum negative signed dividend with negative unit divisor
Stimulus: Combinational application of the minimum negative 32-bit two's-complement value on operand_a with the negative-one two's-complement value on operand_b across all eight muldiv_op selector encodings, accompanied by single-factor neighbor perturbations of operand_a, operand_b, and swapped operand order under the signed quotient and signed remainder selectors
Support/witness path: Direct combinational observation on the public result port driven solely via operand_a, operand_b, and muldiv_op; single-factor neighbor and swapped-operand inputs under signed quotient and signed remainder act strictly as support differential witnesses confirming that overflow substitution activates exclusively on the exact signed-overflow pair
Public observations: With minimum negative signed operand_a and negative-one operand_b, signed quotient outputs the minimum negative 32-bit value on result and signed remainder outputs zero without simulation runtime overflow error; With the same operand pair, unsigned quotient outputs zero, unsigned remainder outputs operand_a, and the four multiplication selectors output their exact lower or upper 32-bit product words on result; Perturbing operand_a by one, perturbing operand_b by one, or swapping operand_a and operand_b under signed quotient and signed remainder produces exact truncated quotients and dividend-signed remainders rather than overflow-substituted values
Forbidden: Accessing internal DUT signals or hierarchy outside the declared public ports operand_a, operand_b, muldiv_op, and result; Driving or referencing nonexistent clock or reset ports; Repeating general multiplication sign-quadrant sweeps or zero-divisor sweeps already witnessed in the passing suite

