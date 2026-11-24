## Publica — incremento 1

Behavior: For a high-bit-set U-immediate, produce the encoded upper bits with twelve low zero bits, without sign extension.
Coverage gap: U-immediate high-bit behavior: the U-immediate is not sign-extended
Prerequisites: none
New factor: U-immediate is not sign-extended
Stimulus: A legal LUI source instruction with the high bit of its U-immediate set.
Support/witness path: None required; the U-immediate is directly observable.
Public observations: Observe imm_u equals the encoded U-immediate with twelve low zero bits.; Observe that imm_u is not sign-extended.
Forbidden: Do not require internal signals or hierarchy.; Do not assert unrelated control outputs or other immediate outputs.; Do not use an illegal or malformed instruction encoding.

## Publica — incremento 2

Behavior: Reconstruct an S-immediate from its split instruction fields.
Coverage gap: S-format immediate reconstruction has no public-port witness.
Prerequisites: No stateful prerequisites; the passing suite already establishes combinational settling and public immediate-output observation.
New factor: S-immediate reconstruction
Stimulus: Use a legal store instruction with a negative offset and distinguishable values in the split immediate fields.
Support/witness path: None; the legal store instruction directly carries the focal immediate.
Public observations: Observe that imm_s matches the encoded S-immediate with the required sign extension.
Forbidden: Do not inspect internals or assert store-control behavior; do not use an illegal or malformed instruction encoding.

## Publica — incremento 3

Behavior: The B-immediate output reconstructs the encoded branch displacement with bit zero equal to zero.
Coverage gap: B-immediate extraction: no public-port witness checks reconstruction from the B-format instruction fields or its implicit zero bit.
Prerequisites: The suite already has public witnesses for I- and S-immediate sign extension and U-immediate extraction.; A legal branch instruction can be assembled and its immediate output observed directly.
New factor: B-format immediate reconstruction
Stimulus: A legal branch instruction targeting a forward label at a positive, nonzero displacement, chosen so the encoded B-immediate fields are distinguishable.
Support/witness path: None; the branch instruction directly exposes the B-immediate output.
Public observations: Observe imm_b equal to the branch displacement reconstructed from the specified B-format bit mapping.; Observe that imm_b bit zero is zero.
Forbidden: Do not require internal signals or control-unit implementation details.; Do not use illegal or malformed instruction encodings.; Do not count branch control decoding as newly covered by this immediate-focused case.

## Publica — incremento 3

Behavior: A valid LUI asserts reg_write.
Coverage gap: Valid LUI register-write decoding has no public-port witness.
Prerequisites: A legal LUI stimulus is already present in the approved high-U-immediate case.
New factor: LUI register-write assertion
Stimulus: Use a legal LUI instruction.
Support/witness path: Direct observation; no support sequence is needed.
Public observations: Observe reg_write asserted for the valid LUI.
Forbidden: Do not inspect internal signals or use malformed, reserved, or illegal instruction encodings.

## Publica — incremento 4

Behavior: Generate imm_b from the specified instruction bits.
Coverage gap: B-immediate reconstruction, including sign extension and the implicit zero low bit
Prerequisites: none
New factor: B-immediate reconstruction
Stimulus: Use a legal branch instruction with a negative immediate and distinguishable contributing immediate fields.
Support/witness path: None; observe imm_b directly.
Public observations: imm_b equals the sign-extended B-immediate reconstructed from the instruction fields.; imm_b bit 0 is zero.
Forbidden: Do not claim branch-control decoding as covered by this case.; Do not require internal signals.

