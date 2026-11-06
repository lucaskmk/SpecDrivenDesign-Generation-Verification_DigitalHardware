## Publica — incremento 1

Behavior: MUL returns the low 32 bits of a product whose high 32 bits are also nonzero and differ from the low word.
Coverage gap: MUL low-word selection when the full product has nonzero, distinct high and low words
Prerequisites: A passing public-port MUL result witness exists.
New factor: Product has a nonzero high word distinct from its low word.
Stimulus: Select MUL and use operands whose product has nonzero, unequal high and low words.
Support/witness path: 
Public observations: The public result equals the product’s low 32-bit word.
Forbidden: Do not require internal signals or hierarchy.; Do not count selector decoding or another operation as covered.

## Publica — incremento 2

Behavior: For MULHU, return bits 63:32 of the unsigned product.
Coverage gap: MULHU unsigned high-word product selection
Prerequisites: The suite already witnesses MUL low-word multiplication. No additional prerequisite is needed.
New factor: Unsigned high-word product selection
Stimulus: Select MULHU with one operand whose top bit is set and another whose top bit is clear, choosing magnitudes that make the unsigned product's high word nonzero.
Support/witness path: None.
Public observations: After combinational settling, compare the public result port with the high word of the unsigned product from an independent reference calculation.
Forbidden: Do not inspect internals, require exhaustive operand coverage, or count the existing MUL witness as evidence for MULHU.

## Publica — incremento 3

Behavior: MULH returns the high 32 bits of the signed product.
Coverage gap: MULH signed multiplication: the high word of a signed-by-signed product is not yet witnessed.
Prerequisites: MUL low-word behavior has a public-port witness.; Unsigned high-word multiplication has a public-port witness.
New factor: Signed interpretation of MULH operands.
Stimulus: Select MULH with one negative operand and one positive operand, choosing magnitudes that produce a nonzero high word.
Support/witness path: None; the result directly witnesses the focal behavior through the public result port.
Public observations: The result equals the high 32 bits of the signed product.
Forbidden: Do not inspect implementation internals.; Do not add other multiplication modes or division/remainder behaviors to this case.

