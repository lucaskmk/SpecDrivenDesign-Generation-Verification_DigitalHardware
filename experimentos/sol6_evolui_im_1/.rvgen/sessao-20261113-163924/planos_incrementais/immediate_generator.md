## Publica — incremento 6

Behavior: imm_s extends a negative store displacement's sign through its upper bits.
Coverage gap: S-type negative sign extension has no public-port witness.
Prerequisites: The passing suite witnesses positive nonuniform S-type field assembly and negative sign extension on I- and B-type outputs.
New factor: S-type negative sign extension
Stimulus: A legal store with a negative nonuniform displacement whose encoded lower displacement bits match the previously witnessed positive store displacement.
Support/witness path: No support sequence is needed; the prior positive store is the comparison witness.
Public observations: Observe imm_s through its declared port. Check that its displacement bits retain the witnessed split-field pattern and its upper bits are sign-filled.
Forbidden: Do not inspect internals, use an illegal encoding, or claim coverage of another output from this case.

## Publica — incremento 7

Behavior: imm_j[0] is zero for a legal JAL instruction.
Coverage gap: The constant-zero least significant bit of the J-type immediate has no public-port witness.
Prerequisites: The passing suite already witnesses the analogous constant-zero bit of imm_b.
New factor: J-type implicit low bit
Stimulus: A legal JAL instruction targeting a nearby forward label.
Support/witness path: Support: assemble the JAL from legal RV32IM source and present its instruction word through instr. This establishes a J-type input; it is not counted as separate coverage.
Public observations: Observe imm_j[0] through the declared output port and require it to be zero.
Forbidden: Do not inspect internals, use an illegal encoding, or count the support assembly as a second behavior.

## Publica — incremento 8

Behavior: A negative J-type displacement one-fills the sign-extension region of imm_j.
Coverage gap: J-type negative sign extension has no public-port witness.
Prerequisites: The passing suite already witnesses negative sign extension for other immediate types and the constant-zero low bit of imm_j.
New factor: J-type negative sign extension
Stimulus: A legal backward JAL to an earlier label, giving a negative displacement.
Support/witness path: Support: place a labeled instruction before the backward JAL so assembly can resolve the displacement. Present the assembled JAL through instr; do not count the labeled instruction as new coverage.
Public observations: After combinational propagation, check that the sign-extension region of imm_j is one-filled. Do not claim coverage of its split-field mapping from this observation.
Forbidden: Do not inspect internals, use a clock or reset, use an illegal encoding, or count support instructions as evidence.

## Publica — incremento 9

Behavior: The separated instruction fields are assembled in the correct order into the branch immediate.
Coverage gap: B-type split-field mapping for a nonuniform displacement
Prerequisites: Passing public-port witnesses already establish branch sign extension and the implicit zero low bit.
New factor: B-type split-field reassembly
Stimulus: A legal forward conditional branch with a positive, nonuniform displacement that exercises each separated B-type source slice.
Support/witness path: Support: assemble the legal branch and present its instruction word at instr. This establishes the stimulus; it is not additional coverage.
Public observations: Compare the complete imm_b output against the branch displacement independently determined from the assembly source.
Forbidden: Do not inspect internals, use malformed encodings, or count the assembly support as a new behavior.

