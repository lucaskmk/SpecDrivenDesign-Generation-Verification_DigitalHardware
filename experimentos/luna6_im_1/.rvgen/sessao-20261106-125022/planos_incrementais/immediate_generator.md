## Publica — incremento 1

Behavior: With instr[31] clear, imm_i has zeroes in bits 31:12 and preserves instr[30:20] in bits 11:0.
Coverage gap: I-immediate zero extension when instr[31] is clear
Prerequisites: The passing suite witnesses imm_i sign extension for a sign-set immediate.
New factor: I-immediate zero extension
Stimulus: Use a sign-set I-immediate pattern as support, then use the otherwise identical input with instr[31] clear and instr[30:20] nonzero.
Support/witness path: The sign-set input is support, reusing the existing imm_i sign-extension witness. Change only instr[31] for the target input.
Public observations: For the target input, imm_i[31:12] is zero.; For the target input, imm_i[11:0] matches instr[30:20].
Forbidden: Do not require or inspect internal signals.; Do not assert unrelated immediate outputs as additional coverage.; Do not count the sign-set support input as newly covered behavior.

## Publica — incremento 2

Behavior: A U-format immediate preserves instr[31:12] in imm_u[31:12] and produces zero in imm_u[11:0].
Coverage gap: U-immediate packing has no public-port witness.
Prerequisites: none
New factor: U-immediate packing.
Stimulus: Use a legal LUI source with a mixed upper-immediate pattern whose top source bit is set.
Support/witness path: 
Public observations: Observe imm_u and check that its upper 20 bits match the LUI immediate field and its lower 12 bits are zero.
Forbidden: Do not require internal signals.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.; Do not assert unrelated immediate outputs as additional focal behaviors.

## Publica — incremento 3

Behavior: The S immediate places instr[31:25] in bits 11:5 and instr[11:7] in bits 4:0, then extends the sign.
Coverage gap: S-immediate source-field mapping
Prerequisites: none
New factor: S-immediate source-field mapping
Stimulus: Use a legal SW source instruction with sign bit clear and distinct nonzero values in the upper and lower S-immediate source fields.
Support/witness path: None; the S immediate is directly observable through imm_s.
Public observations: Check that imm_s equals the zero-extended S immediate assembled from the instruction's two S-format source fields.
Forbidden: Do not inspect implementation internals.; Do not use illegal or malformed instruction encodings.; Do not claim coverage of S-immediate sign extension for a set sign bit, B or J rearrangement, or input-bit independence.

## Publica — incremento 4

Behavior: imm_s sign-extends its sign bit through bits 31:12 while preserving the immediate's low 12 bits.
Coverage gap: S-format sign extension for a negative immediate
Prerequisites: The passing SW witness establishes the S-immediate source-field mapping for a positive immediate.; The public instr input and imm_s output make the negative-immediate result directly observable.
New factor: S-immediate sign extension
Stimulus: A legal SW instruction with the same low eleven S-immediate bits as the existing positive-offset SW witness, but with a representable negative offset.
Support/witness path: Use the existing positive-offset SW mapping witness as the comparison. No additional support sequence is needed.
Public observations: Check imm_s[31:12] is sign-extended for the negative immediate.; Check imm_s[11:0] retains the immediate bits established by the existing mapping witness.
Forbidden: Do not inspect implementation internals.; Do not assert unrelated immediate outputs.; Do not use an illegal or malformed instruction encoding.

