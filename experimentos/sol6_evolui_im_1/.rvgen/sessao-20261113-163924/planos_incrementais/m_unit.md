## Publica — incremento 1

Behavior: MULH returns the high half of the full signed product.
Coverage gap: MULH signed high-half multiplication has no public-port witness.
Prerequisites: The passing suite already witnesses MUL with a positive first operand and a negative second operand.
New factor: MULH signed high-half result
Stimulus: Signed high-half multiplication using the operand pair already witnessed for low-half multiplication.
Support/witness path: Reuse the witnessed operand pair and select MULH through funct3. No support sequence is needed.
Public observations: With both operands unchanged, result matches the independently calculated high half of their signed product and differs from the witnessed MUL result.
Forbidden: Do not inspect internals, use an illegal instruction encoding, or count the existing MUL witness as new coverage.

## Publica — incremento 2

Behavior: The result is the high half of the full product with operand_a interpreted as signed and operand_b as unsigned.
Coverage gap: MULHSU mixed-signedness high-product result
Prerequisites: MUL low-product result has a passing public-port witness.; MULH signed high-product result has a passing public-port witness for the same operands.
New factor: Unsigned interpretation of the second multiplication operand
Stimulus: Select MULHSU with the unequal operands already used by the passing MULH case: a positive first operand and a negative-bit-pattern second operand.
Support/witness path: No support sequence is needed; compare the combinational result with an independent mixed-signedness product calculation.
Public observations: The settled result equals the calculated high product half.; That result differs from the signed-by-signed high half already witnessed for these operands.
Forbidden: Do not inspect internal signals.; Do not substitute an illegal instruction encoding or require a clock or reset.; Do not count the existing MULH witness as newly covered.

## Publica — incremento 3

Behavior: MULHU returns the upper 32 bits of the full unsigned product.
Coverage gap: MULHU unsigned × unsigned high-half result
Prerequisites: The passing suite witnesses MUL's low half, MULH's signed high half, and MULHSU's mixed-signedness high half.
New factor: Unsigned interpretation of the first operand
Stimulus: Select MULHU with unequal operands whose sign bits are both set and whose unsigned product has a nonzero upper half.
Support/witness path: No support sequence is needed; drive the declared inputs and observe the combinational result.
Public observations: Compare result with an independent unsigned full-product calculation. Choose operands for which that high half differs from the signed-first-operand high half.
Forbidden: Do not inspect internals, use illegal instruction encodings, or count a different operand pair that preserves the existing MULHSU causal relation as new evidence.

## Publica — incremento 4

Behavior: DIVU returns the unsigned quotient of operand_a divided by operand_b.
Coverage gap: Ordinary unsigned division with a nonzero divisor has no public-port witness.
Prerequisites: The passing MULHU case already witnesses both operands as full-width unsigned values through public ports.
New factor: Unsigned quotient
Stimulus: Select DIVU with the unequal negative-bit-pattern operand pair already used by the passing MULHU case. The first operand is larger under unsigned interpretation, and the division is inexact.
Support/witness path: No support sequence is needed; drive the declared inputs and observe the settled result.
Public observations: The result matches an independent unsigned-division reference and differs from the signed quotient for the same operands.
Forbidden: Do not inspect internals, require a clock or reset, or count the existing multiplication witness as new coverage.

