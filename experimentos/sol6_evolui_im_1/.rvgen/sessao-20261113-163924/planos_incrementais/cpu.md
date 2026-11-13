## Publica — incremento 6

Behavior: A valid SB exposes the byte-width code on data_width.
Coverage gap: Byte-store data_width code
Prerequisites: The passing suite already witnesses that SB asserts data_write.
New factor: Byte-store width selection
Stimulus: A legal byte store using zero-valued base and source registers.
Support/witness path: No additional support sequence is needed; observe the store through the public data interface.
Public observations: While the byte store asserts data_write, data_width identifies a byte access.
Forbidden: Do not inspect internal signals or treat the existing write-enable witness as evidence of width selection.

## Publica — incremento 7

Behavior: A valid SH instruction exposes the halfword width code on data_width.
Coverage gap: Halfword store width selection has no public-port witness.
Prerequisites: The passing suite witnesses store write enable and byte-width selection for SB.
New factor: Halfword store width selection
Stimulus: A naturally aligned SH using the zero register as its base and source.
Support/witness path: No prior register state is needed; the store's bus outputs directly witness the focal behavior.
Public observations: During the SH instruction, data_width indicates halfword width.
Forbidden: Do not inspect internal signals.; Do not count store write enable as newly covered.

## Publica — incremento 8

Behavior: SB exposes rs1 plus its S immediate as a byte address, retaining the low address bits.
Coverage gap: Unmasked byte effective address for a store with a nonzero S immediate
Prerequisites: Passing public-port witnesses already establish asynchronous PC reset, SB write enable, and SB byte width. They do not establish store address calculation.
New factor: Store effective-address calculation
Stimulus: An SB from the zero register to a nonzero, naturally aligned byte displacement from the zero base register.
Support/witness path: Support: reset to select the SB instruction. Observe the store transaction directly; no register-result witness is needed.
Public observations: The store asserts data_write, and data_addr equals the nonzero byte displacement rather than its word-aligned base.
Forbidden: Do not inspect internal signals, add a register-setup sequence, test a different width mapping, or use an illegal instruction.

## Publica — incremento 9

Behavior: A valid SW exposes the word-width code on data_width.
Coverage gap: SW word-width selection has no public-port witness.
Prerequisites: SB store enable has a passing public-port witness.; SB and SH width selection have passing public-port witnesses.
New factor: SW word-width selection
Stimulus: A naturally aligned SW using zero-valued base and source registers.
Support/witness path: Present the assembled SW through instr_data and observe its bus outputs while it is the current instruction. The store indication only establishes that the width observation belongs to a valid store; it is not new coverage.
Public observations: data_write indicates a store.; data_width indicates a word access.
Forbidden: Do not inspect internal signals.; Do not treat store payload, memory commit, or register state as newly covered.; Do not use an illegal or malformed instruction encoding.

