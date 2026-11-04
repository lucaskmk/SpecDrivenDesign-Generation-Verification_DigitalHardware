## Publica — incremento 1

Behavior: When the I-immediate sign bit is clear, imm_i has zero-filled upper bits.
Coverage gap: I-immediate zero-filled sign extension when instr[31] is 0
Prerequisites: The I-immediate output is already observed through the public interface.; The passing suite already witnesses the opposite sign-extension case.
New factor: Zero-filled sign extension of the I immediate
Stimulus: Use a legal ADDI with a positive odd immediate, so the I-immediate sign bit is clear and its low source bit is nonzero.
Support/witness path: None; the behavior is directly observable on imm_i.
Public observations: Observe imm_i.; Check that its upper bits are zero and its low bit reflects the nonzero immediate.
Forbidden: Do not require internal signals or hierarchy access.; Do not use a clock or reset.; Do not treat opcode variation or other immediate outputs as newly covered by this case.

## Publica — incremento 2

Behavior: imm_u copies instr[31:12] into its upper 20 bits and has zeroes in its lower 12 bits.
Coverage gap: U-type immediate extraction is not yet observed on a public output.
Prerequisites: none
New factor: U-type immediate extraction
Stimulus: Use a legal ADDI with a nonzero upper instruction slice, so the U-type output is nontrivial.
Support/witness path: None; the legal ADDI is the stimulus for the focal behavior.
Public observations: Observe imm_u and compare it with the zero-extended instr[31:12] slice.
Forbidden: Do not inspect implementation internals.; Do not use illegal or malformed instruction encodings.; Do not assert unrelated immediate outputs.

## Publica — incremento 3

Behavior: Reconstruct the S-type immediate from its two specified instruction slices.
Coverage gap: S-type immediate reconstruction from its split instruction fields has no public-port witness.
Prerequisites: The passing ADDI cases establish combinational stimulus and observation through declared ports.; No prior state or support sequence is required.
New factor: S-type split-field immediate reconstruction
Stimulus: Use a legal store instruction with a positive, nonuniform immediate whose bits exercise both S-type immediate slices.
Support/witness path: 
Public observations: Observe imm_s and compare it with the sign-extended S-type immediate specified by the contract.
Forbidden: Do not inspect internal signals.; Do not use an illegal or malformed instruction encoding.; Do not count other immediate outputs as newly covered by this case.

## Publica — incremento 4

Behavior: imm_b[0] remains zero for a legal B-type instruction with a nonzero aligned branch displacement.
Coverage gap: The B-type immediate's implicit low bit is zero.
Prerequisites: The suite already drives legal instruction inputs and observes public immediate outputs.; No additional behavior prerequisite.
New factor: B-type implicit low bit is zero.
Stimulus: Use a legal conditional-branch source accepted by assemble_rv32i, with a nonzero aligned displacement.
Support/witness path: 
Public observations: Observe imm_b through its declared public output.; Assert only that imm_b[0] is zero.
Forbidden: Do not require internal signals or hierarchy.; Do not use an illegal or malformed instruction encoding.; Do not assert unrelated immediate mappings or opcode-independence behavior.

