## Publica — incremento 1

Behavior: For funct3 selecting MULH, result is bits 63:32 of the signed product.
Coverage gap: MULH: signed-by-signed high-half product
Prerequisites: none
New factor: Signed high-half multiplication
Stimulus: Select MULH using the passing smoke test's operands, for which signed and unsigned high-half products differ.
Support/witness path: None; the public result directly witnesses the selected product half.
Public observations: The result equals the upper 32 bits of the signed product.; The observed result distinguishes signed high-half multiplication from unsigned high-half multiplication.
Forbidden: Requiring internal signals or hierarchy access.; Using illegal, reserved, or malformed instruction encodings.

## Publica — incremento 2

Behavior: For funct3 selecting MULHSU, return bits [63:32] of the product with operand_a interpreted as signed and operand_b as unsigned.
Coverage gap: MULHSU high-half signed-by-unsigned product
Prerequisites: The public-port suite already witnesses a low-half MUL result.; The public-port suite already witnesses a signed-by-signed MULH high half for the same operand pair proposed below.
New factor: MULHSU signed-by-unsigned high-product interpretation
Stimulus: Use the existing high-product operand pair: operand_a has the bit pattern for negative one, and operand_b has its high bit set. Select MULHSU.
Support/witness path: None; the operands and selector directly exercise the focal behavior.
Public observations: After combinational settling, result equals the upper 32 bits of the signed-operand_a by unsigned-operand_b product.; The result differs from the already witnessed MULH result for this pair.
Forbidden: Do not inspect implementation internals.; Do not require exhaustive selector enumeration or additional operand combinations.

## Publica — incremento 3

Behavior: For funct3 selecting MULHU, return bits 63:32 of the unsigned product.
Coverage gap: MULHU: unsigned-by-unsigned high product half
Prerequisites: None; the public combinational inputs and result are sufficient.
New factor: Unsigned-by-unsigned high-half product selection.
Stimulus: Select MULHU for operands with their top bits set and with an unsigned high product half that differs from both signed high-product results.
Support/witness path: 
Public observations: After combinational settling, result matches the independently computed upper 32 bits of the unsigned product.
Forbidden: Do not inspect hierarchy or require internal signals. Do not count existing MUL, MULH, or MULHSU witnesses as newly covered.

## Publica — incremento 4

Behavior: The selected unsigned division operation returns the unsigned quotient.
Coverage gap: Ordinary unsigned division with a nonzero divisor (DIVU)
Prerequisites: No functional arithmetic prerequisites. The suite already demonstrates driving the public inputs, allowing combinational settling, and checking the public result.
New factor: Unsigned quotient semantics for a nonzero divisor.
Stimulus: Select the DIVU operation and use a high-bit-set dividend with a nonzero divisor chosen so its unsigned quotient differs from the quotient under signed interpretation.
Support/witness path: None; the quotient is directly observable on the public result port.
Public observations: Check that result equals the unsigned quotient for the selected operands.
Forbidden: Do not inspect implementation internals.; Do not combine this case with remainder, signed division, division by zero, or overflow behavior.; Do not add additional operation selections or operand scenarios to this case.

