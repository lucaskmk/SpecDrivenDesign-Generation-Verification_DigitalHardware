## Publica — incremento 1

Behavior: When a legal ADDI has a negative immediate, imm_i copies the sign bit into its upper bits.
Coverage gap: I-immediate sign extension from a legal instruction
Prerequisites: none
New factor: I-immediate sign extension
Stimulus: Use a legal ADDI with a negative immediate whose low bits have a distinct pattern.
Support/witness path: None; the instruction directly exposes the I immediate.
Public observations: imm_i(11 downto 0) matches the ADDI immediate bits.; imm_i(31 downto 12) consists of copies of instr(31).
Forbidden: Do not use the current smoke input as evidence: its opcode is not a legal RV32IM instruction encoding.; Do not require internal signals or assert unrelated immediate formats.

## Publica — incremento 2

Behavior: The upper bits of imm_i are zero when the I-immediate sign bit is zero.
Coverage gap: I-immediate zero sign-extension edge: instr[31] = 0
Prerequisites: A passing ADDI case already witnesses I-immediate mapping and sign extension when instr[31] = 1.
New factor: instr[31] = 0
Stimulus: A legal ADDI with a positive, nonzero immediate.
Support/witness path: 
Public observations: Observe through imm_i that bits 31:12 are all zero.
Forbidden: Do not require implementation internals.; Do not claim coverage of other immediate formats or exhaustive I-immediate packing.

## Publica — incremento 3

Behavior: The U immediate preserves the instruction's upper immediate bits while keeping imm_u[11:0] zero, even when the top source bit is 1.
Coverage gap: U-immediate zero extension when instr[31] is 1
Prerequisites: Combinational outputs settle after an input assignment, as demonstrated by the passing I-immediate cases.; Use a legal LUI source accepted by assemble_rv32im.
New factor: U-immediate zero extension with the top source bit set
Stimulus: Apply a legal LUI whose upper-immediate value has its top bit set and all other upper-immediate bits clear.
Support/witness path: None required.
Public observations: Observe imm_u[31] is 1.; Observe imm_u[11:0] is zero.
Forbidden: Do not use an unsupported or illegal instruction encoding.; Do not require internal signals or exhaustive U-bit enumeration.

## Publica — incremento 4

Behavior: Reconstruct the S immediate from its two instruction fields.
Coverage gap: S-immediate split-field reconstruction is not witnessed through imm_s.
Prerequisites: Passing tests already demonstrate combinational immediate outputs after an instruction is applied.; Passing tests already use legal RV32IM assembly stimuli.
New factor: S-immediate reconstruction
Stimulus: Use a legal store instruction with a positive, non-symmetric offset whose low and high S-immediate fragments contain distinct set bits.
Support/witness path: 
Public observations: Observe imm_s through the declared output port and compare it with the assembled store offset, including the required zero sign-extension bits.; Do not claim coverage of other immediate formats from this case.
Forbidden: Do not inspect implementation internals.; Do not use illegal or malformed instruction encodings.; Do not enumerate every S-immediate source bit.

