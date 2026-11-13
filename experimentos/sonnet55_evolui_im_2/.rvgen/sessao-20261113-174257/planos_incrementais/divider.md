## Publica — incremento 1

Behavior: With is_signed=1 and the operands held at the smoke case (dividend -7, divisor 2), setting want_rem=1 makes result the signed remainder. The remainder has the sign of the dividend, and its value differs from the quotient and from both operands.
Coverage gap: Strategy group 1 (operation selector): want_rem selecting the remainder instead of the quotient. The only current witness is a signed quotient (want_rem=0), so the remainder output path has no public-port evidence.
Prerequisites: The smoke test already shows that the combinational divider settles and returns the signed quotient for this operand pair, so the same pair can be reused with only want_rem changed.
New factor: want_rem selecting the remainder output
Stimulus: Scenario class: signed division with ordinary non-zero operands, both of which are neither special cases nor overflow. Hold the smoke operands (dividend -7, divisor 2, is_signed=1) fixed and change only want_rem from quotient to remainder. The reference model gives a remainder of -1 as a 32-bit two's-complement pattern.
Support/witness path: No support sequence is needed. result is directly observable on the public port after settling, and the smoke quotient is the baseline for the single-factor comparison.
Public observations: After settling, all 32 bits of result equal the model remainder for the signed pair (-7, 2). This value differs from the quotient already witnessed (-3), from the dividend, and from the divisor, so a wrong selection cannot pass by coincidence.
Forbidden: Do not change the operands or is_signed in this case. Do not repeat the quotient check. Do not add unsigned, divisor-zero, overflow, operand-swap or sign-combination coverage here. Do not read internal signals, and do not drive undefined values ('U', 'X', 'Z', and so on).

## Publica — incremento 2

Behavior: With the operand bit patterns held fixed at 0xFFFFFFF9 (dividend) and 0x00000002 (divisor), clearing is_signed switches the division from signed (-7/2) to unsigned (4294967289/2). The quotient therefore changes from the signed value to the unsigned value.
Coverage gap: Operation selector, group 1: is_signed has no witness. All current evidence uses is_signed='1'. Nothing shows that clearing is_signed makes both operands unsigned, so bit 31 is read as a large positive value.
Prerequisites: Smoke test: signed DIV of 0xFFFFFFF9 / 0x00000002 gives 0xFFFFFFFD, so the quotient path and these operands are already witnessed.; Approved case: signed REM of the same operands gives 0xFFFFFFFF, so want_rem selection is witnessed.
New factor: is_signed changes from 1 to 0 (unsigned operand interpretation)
Stimulus: Reuse the signed -7 / 2 operand pair from the existing suite. Apply it first with is_signed='1' and want_rem='0' as the signed baseline, then change only is_signed to '0'. Leave want_rem='0', both operands and all other inputs unchanged, then let the combinational output settle. Only the quotient is checked, because the one new behavior is the interpretation change.
Support/witness path: None needed. result is directly observable on the public port. The signed baseline is already covered by the smoke test and is only reapplied as the comparison point, not counted as new coverage.
Public observations: After settling, result equals the unsigned quotient 0x7FFFFFFC. This is the reference-model value for 0xFFFFFFF9 / 0x00000002 unsigned.; result differs from the signed quotient 0xFFFFFFFD observed with the same operand bits and is_signed='1'.; result is distinct from both operands, so a wrong source cannot pass by coincidence.
Forbidden: Changing want_rem, the operand values, or both selectors in the same case; Adding a swapped-operand, divisor-zero, overflow, or sign-combination scenario; Using a non-negative operand pair, where signed and unsigned results are identical and prove nothing; Using a clock, a reset, or any internal signal; Computing encodings, hex literals, Python, Cocotb steps, or clock edges in this plan; Repeating the signed -7 / 2 quotient or remainder relation as the focal check

## Publica — incremento 3

Behavior: With is_signed='0' and want_rem='1', result is the unsigned remainder of operand_a / operand_b, with bit 31 of the dividend treated as a large positive magnitude. It is not the unsigned quotient, the signed remainder, or either operand.
Coverage gap: Strategy group 1 (operation selector): the unsigned remainder combination (is_signed='0', want_rem='1', REMU) has no public-port witness. The suite covers signed DIV (smoke), signed REM (lote-001) and unsigned DIV (lote-002), but never reads the unsigned remainder output.
Prerequisites: Signed DIV on the pair -7 / 2 has a passing witness (smoke).; want_rem 0 -> 1 selects the remainder in signed mode (lote-001).; is_signed 1 -> 0 gives the unsigned quotient for the same bit patterns (lote-002).; Combinational settling after an input change is already exercised by the existing tests.
New factor: want_rem selects the remainder while is_signed is '0'
Stimulus: Reuse the operand bit patterns already in the suite: dividend with bit 31 set (the pattern read as -7 in signed mode) and divisor 2. Start from the already-witnessed unsigned-quotient state (is_signed='0', want_rem='0') and change only want_rem to '1'. The unsigned remainder is 1. It differs from the unsigned quotient (0x7FFFFFFC), from the signed remainder (0xFFFFFFFF), and from both operands.
Support/witness path: none: the focal behavior is directly observable on result. The unsigned-quotient baseline is a comparison point only and is not counted as new coverage.
Public observations: result equals 0x00000001 after settling with is_signed='0' and want_rem='1'.; result differs from the unsigned quotient 0x7FFFFFFC obtained with want_rem='0'.; result differs from the signed remainder 0xFFFFFFFF, so a signed-remainder path wrongly used in unsigned mode would fail.; result differs from operand_a and operand_b.
Forbidden: Divisor-zero, signed-overflow, operand-swap and sign-combination cases (separate semantic factors).; Changing the operand magnitudes or adding new operand pairs.; Sweeping operands or random vectors.; Reading internal signals.; Driving 'U', 'X', 'Z' or other undefined values.; Using a clock or reset (the entity has none).; Binary literals in the test.

## Publica — incremento 4

Behavior: With selectors held fixed, the quotient of operand_a / operand_b is not equal to the quotient of the swapped pair. For small positive operands (100 / 7) the quotient is 14. After exchanging the two operand values (7 / 100) the quotient is 0.
Coverage gap: Strategy group 2, operand roles: no public-port witness yet shows that operand_a is the dividend and operand_b is the divisor. Every passing test uses the same -7/2 pair, which is only ever applied in one orientation. A swapped-operand fault is therefore undetected.
Prerequisites: The selector paths for DIV, REM, DIVU and REMU on -7/2 are already witnessed as passing. Combinational settling after an input change is already witnessed. Ordinary non-special arithmetic with a non-zero divisor and no signed overflow is already exercised.
New factor: Exchanging which operand value is on operand_a and which is on operand_b
Stimulus: Hold is_signed and want_rem fixed in quotient mode, with both operands non-negative and small. First apply dividend 100 and divisor 7 and let the output settle. Then change only the operand values by exchanging them, so dividend is 7 and divisor is 100, and let the output settle again. The first quotient (14) differs from the dividend, the divisor and the swapped result. The second quotient is 0.
Support/witness path: None needed. Both operand orientations are observed directly on result.
Public observations: Drive only operand_a, operand_b, is_signed and want_rem, then read result after settling. For 100 / 7, result is the full 32-bit value 14. For 7 / 100, result is the full 32-bit value 0. The two results differ, and the first result differs from both operand values.
Forbidden: Do not add the remainder or other selector combinations. Do not add sign combinations, divisor zero, signed overflow or bit-31 operands. Do not add repeated operand pairs such as 1000/30, or random or sweep vectors. Do not use any clock, reset or internal signals. Do not pick a pair where the quotient equals an operand or the swapped quotient.

