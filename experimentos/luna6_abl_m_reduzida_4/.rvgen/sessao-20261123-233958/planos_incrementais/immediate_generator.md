## Publica — incremento 1

Behavior: A clear sign bit produces zero in imm_i[31:12].
Coverage gap: I-immediate zero-filled upper bits when instr[31] is clear
Prerequisites: The passing suite witnesses imm_i sign extension when instr[31] is set.
New factor: Clear-sign behavior for the I immediate.
Stimulus: Apply a word with instr[31] clear and a nonzero I-immediate payload.
Support/witness path: None required.
Public observations: Observe through imm_i that the upper bits are zero.
Forbidden: Do not require internal signals.; Do not count the existing set-sign I-immediate witness as new coverage.; Do not claim coverage of other immediate formats or routing behavior from this case.

## Publica — incremento 2

Behavior: A U-immediate payload bit maps to the corresponding output bit twelve positions higher.
Coverage gap: U-immediate payload routing for a non-sign source bit
Prerequisites: None beyond the declared public interface; existing tests establish combinational settling.
New factor: U-immediate payload placement
Stimulus: A legal LUI with exactly one non-sign U-immediate payload bit set.
Support/witness path: No support sequence is needed; observe imm_u directly.
Public observations: The corresponding shifted bit of imm_u is set, with no other imm_u bit set.
Forbidden: Do not inspect internals, use an illegal or malformed instruction, or count unrelated output behavior as newly covered.

## Publica — incremento 3

Behavior: imm_s combines instr[31:25] with instr[11:7] in their specified positions and zero-fills its upper bits when instr[31] is clear.
Coverage gap: S-immediate source-field routing into imm_s
Prerequisites: None. The existing cases establish public-port combinational observation and include a clear-sign immediate witness.
New factor: S-immediate field assembly
Stimulus: Apply a legal LUI source accepted by assemble_rv32im, choosing its immediate and destination-register fields so the two source portions used by imm_s have distinct, nonzero patterns and instr[31] is clear.
Support/witness path: None; the LUI is the focal stimulus, not a support sequence.
Public observations: After combinational settling, observe imm_s and assert that it equals the value formed from the instruction's specified S-immediate source bits, with zero-filled upper bits. Assert no unrelated outputs.
Forbidden: Do not inspect internals, use an illegal or malformed encoding, or count the LUI behavior or other immediate outputs as newly covered.

## Publica — incremento 4

Behavior: The instruction bit at position 31 maps to imm_u[31]; it does not cause sign extension.
Coverage gap: U immediate bit 31 as payload rather than a sign bit
Prerequisites: The suite already witnesses U-immediate payload routing with a lower payload bit and witnesses sign extension for I immediates. No state or additional support behavior is required.
New factor: U immediate bit 31 is payload, not sign extension.
Stimulus: Use a legal LUI with the top bit of its U-immediate payload set and a nonzero destination.
Support/witness path: None; observe the result directly through the public imm_u output.
Public observations: Assert that imm_u[31] is set.
Forbidden: Do not inspect hierarchy or internals, require opcode decoding, or assert unrelated immediate behaviors.

