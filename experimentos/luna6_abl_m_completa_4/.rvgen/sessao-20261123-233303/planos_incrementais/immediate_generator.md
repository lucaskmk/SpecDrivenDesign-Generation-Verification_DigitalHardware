## Publica — incremento 1

Behavior: I-type zero-sign extension
Coverage gap: I-type immediate with a zero sign bit, which should zero-fill the upper extension bits
Prerequisites: The passing suite demonstrates the I-type output for a sign-bit-one input.; The passing suite demonstrates combinational settling through the public interface.
New factor: Zero-sign I-type extension
Stimulus: Use a legal ADDI instruction with a nonnegative immediate and asymmetric immediate payload.
Support/witness path: 
Public observations: Observe imm_i through the declared output port.; Check that imm_i upper extension bits are zero.
Forbidden: Do not inspect implementation internals.; Do not use an illegal or reserved instruction encoding.; Do not claim coverage of other immediate formats from this case.

## Publica — incremento 2

Behavior: For a negative I-type immediate, imm_i sign-extends the immediate's sign bit through the upper output bits.
Coverage gap: I-type sign extension when the immediate sign bit is one
Prerequisites: An approved legal ADDI case already witnesses I-type immediate mapping with a zero sign bit.
New factor: I-type sign extension with a one sign bit
Stimulus: A legal ADDI instruction with a negative immediate.
Support/witness path: 
Public observations: Observe imm_i and verify it equals the signed I-type immediate extended to 32 bits.
Forbidden: Do not use an illegal or malformed instruction encoding.; Do not inspect implementation internals.; Do not assert unrelated immediate outputs.

## Publica — incremento 3

Behavior: U-type immediate extraction copies the instruction's upper 20 bits to imm_u(31 downto 12).
Coverage gap: U-type immediate mapping has no public-port witness.
Prerequisites: none
New factor: U-type immediate extraction
Stimulus: Use a legal LUI instruction with a non-symmetric U-type immediate.
Support/witness path: None; the legal LUI instruction directly provides the witness.
Public observations: After combinational settling, check that imm_u(31 downto 12) matches the instruction's upper 20 bits and imm_u(11 downto 0) is zero.
Forbidden: Do not require or inspect implementation internals.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.; Do not assert unrelated immediate outputs as newly covered behavior.

## Publica — incremento 4

Behavior: Reconstruct the S-type immediate from its split instruction fields.
Coverage gap: S-type immediate split-field reconstruction is not yet witnessed through imm_s.
Prerequisites: none
New factor: S-type split-field reconstruction
Stimulus: Use a legal store instruction with an asymmetric immediate whose split fields are nonzero, and check imm_s against the S-type mapping and sign-extension rule.
Support/witness path: 
Public observations: Observe imm_s through the declared output port after combinational settling.; Assert that its low 12 bits contain the S-type immediate fields in the specified positions and its upper bits follow the immediate sign bit.
Forbidden: Do not inspect internal signals.; Do not use reserved, illegal, unallocated, or malformed encodings.; Do not claim coverage for other immediate types from this case.

