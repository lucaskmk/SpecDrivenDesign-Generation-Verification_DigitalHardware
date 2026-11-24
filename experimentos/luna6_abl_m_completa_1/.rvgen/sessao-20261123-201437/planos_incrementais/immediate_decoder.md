## Publica — incremento 1

Behavior: A set instr[31] appears in imm_u[31], while imm_u[11:0] remains zero.
Coverage gap: U-immediate extraction without sign extension when instr[31] is set
Prerequisites: A driven binary instruction and settled combinational outputs; the existing suite already establishes this setup.
New factor: U is not sign-extended.
Stimulus: Use an instruction pattern with instr[31] set and check the U-immediate output.
Support/witness path: None required.
Public observations: Check imm_u[31] is set and imm_u[11:0] is zero.
Forbidden: Do not inspect internals or require opcode validity. Do not count I-immediate behavior as newly covered.

## Publica — incremento 2

Behavior: The S immediate combines instr[31:25] and instr[11:7] in their specified positions.
Coverage gap: S-immediate packing from its two discontiguous instruction fields
Prerequisites: none
New factor: S-immediate packing
Stimulus: A legal store instruction with a positive S-format displacement whose low and high immediate portions are both nonzero.
Support/witness path: 
Public observations: After the combinational output settles, imm_s equals the store displacement.
Forbidden: Do not require or inspect internal signals.; Do not use an illegal or malformed instruction encoding.; Do not claim this case newly covers sign extension, opcode independence, or other immediate formats.

## Publica — incremento 3

Behavior: A negative S-format immediate is sign-extended in imm_s.
Coverage gap: S-immediate sign extension when its sign bit is set
Prerequisites: The existing legal store case witnesses positive S-immediate packing.; The existing smoke case witnesses sign extension for imm_i.
New factor: S-immediate sign extension with the sign bit set
Stimulus: Use a legal RV32IM store with a negative S-format displacement whose low eleven encoded bits match the existing positive S-immediate witness, changing only the S-immediate sign bit.
Support/witness path: 
Public observations: Observe imm_s through the declared output port.; Check that its upper bits are ones and its low twelve bits match the encoded S immediate.
Forbidden: Do not inspect implementation internals.; Do not count the store instruction itself as newly covered behavior.; Do not assert unrelated immediate outputs as part of this focal case.

## Publica — incremento 4

Behavior: Extract a positive B-format immediate from its split instruction fields, including the implicit low zero bit.
Coverage gap: B-immediate field mapping
Prerequisites: None; the immediate is directly observable from the declared instr and imm_b ports.
New factor: B-immediate extraction
Stimulus: A legal conditional branch with a positive, nonzero even displacement chosen to exercise both split immediate source fields.
Support/witness path: None required.
Public observations: Observe that imm_b equals the branch displacement.
Forbidden: Do not require internal signals, use illegal encodings, or add another immediate format as a focal behavior.

