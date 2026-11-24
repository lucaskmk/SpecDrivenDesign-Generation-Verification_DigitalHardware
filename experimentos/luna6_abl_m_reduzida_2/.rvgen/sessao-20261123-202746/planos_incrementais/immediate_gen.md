## Publica — incremento 1

Behavior: imm_u copies instr(31:12) to imm_u(31:12) and keeps imm_u(11:0) zero, even when instr(31) is set.
Coverage gap: U-immediate zero extension, especially when instr(31) is set. The current suite has a public witness only for imm_i sign extension on one negative I immediate; it does not observe imm_s, imm_b, imm_u, or imm_j.
Prerequisites: none
New factor: U-immediate zero extension
Stimulus: Use a legal LUI source instruction with a non-symmetric upper-immediate field whose top bit is set.
Support/witness path: 
Public observations: Through the public imm_u port, assert that the upper 20 output bits equal the instruction's upper-immediate field.; Assert that the lower 12 output bits are zero.
Forbidden: Do not inspect implementation internals.; Do not count the existing imm_i sign-extension witness as evidence for U-immediate behavior.

## Publica — incremento 2

Behavior: The twelve encoded I-immediate bits appear in the specified positions of imm_i.
Coverage gap: I-immediate source-bit placement for a non-symmetric encoded immediate
Prerequisites: The existing public-port witness covers sign extension of imm_i.
New factor: I-immediate source-bit placement
Stimulus: Use a legal ADDI source with a positive, non-symmetric 12-bit immediate whose encoded bits distinguish positions.
Support/witness path: None; imm_i is directly observable from the instruction input.
Public observations: Assert imm_i equals the sign-extended I immediate derived from the ADDI instruction.
Forbidden: Do not use an illegal or malformed instruction encoding.; Do not require internal signals or assert unrelated immediate outputs as additional focal behaviors.

## Publica — incremento 3

Behavior: imm_s places the encoded upper and lower S-immediate fields in their specified positions.
Coverage gap: S-format immediate reconstruction from its split instruction fields
Prerequisites: The existing tests establish combinational evaluation through the public instr and imm_i/imm_u ports.
New factor: S-format split-field placement
Stimulus: A legal store instruction with a positive, non-symmetric immediate whose two encoded fields are distinguishable.
Support/witness path: 
Public observations: Observe imm_s and assert it equals the immediate encoded by the store.
Forbidden: Do not require internal signals.; Do not claim coverage of sign extension, B/J reconstruction, or the other outputs from this case.

## Publica — incremento 4

Behavior: A negative S immediate is sign-extended through imm_s.
Coverage gap: S-immediate sign extension when the encoded sign bit is set
Prerequisites: The suite already witnesses positive S-immediate split-field placement.; The legal assembler accepts a store with a negative signed 12-bit offset.
New factor: Set the S-immediate sign bit while preserving its other encoded bits.
Stimulus: Use a legal store with a negative S offset whose lower eleven encoded immediate bits match the existing positive split-field store.
Support/witness path: None; the store instruction directly supplies the S immediate.
Public observations: Observe imm_s through the declared output port.; Assert that imm_s contains the assembled S immediate sign-extended to 32 bits, including one-filled upper bits.
Forbidden: Do not inspect implementation internals.; Do not require an invalid or malformed instruction encoding.; Do not assert unrelated immediate outputs.

