## Publica — incremento 1

Behavior: A completed sequential instruction advances the fetch address by one instruction word.
Coverage gap: Sequential PC advancement for a legal instruction
Prerequisites: Asynchronous reset establishes the fetch address at zero, already witnessed by the passing suite.
New factor: Sequential PC advancement
Stimulus: A legal no-op sequential instruction at the reset vector.
Support/witness path: Use the existing reset-to-zero public witness as the starting state. The no-op is only a carrier instruction; do not count its operation as newly covered.
Public observations: instr_addr identifies the reset vector before instruction completion.; After completion, instr_addr identifies the next sequential instruction address.
Forbidden: Do not inspect internal PC or other hierarchy signals.; Do not claim ALU, register-write, or instruction-operation coverage from the carrier instruction.

## Publica — incremento 2

Behavior: A legal byte store asserts data_write.
Coverage gap: A valid store asserting data_write during its instruction cycle.
Prerequisites: Reset places instr_addr at zero.; A sequential instruction advances the fetch address.
New factor: Valid-store write-enable assertion.
Stimulus: Present a legal byte-store instruction using x0 as its base and source register.
Support/witness path: 
Public observations: data_write is asserted for the store instruction.
Forbidden: Do not inspect internal CPU signals or registers.; Do not assert unrelated store address, width, payload, or memory-commit behavior as additional focal behaviors.

## Publica — incremento 3

Behavior: Suppress data_write for a valid non-store instruction.
Coverage gap: A valid non-store instruction does not assert data_write during its instruction cycle.
Prerequisites: Reset places the fetch address at zero.; A valid instruction is available at the current fetch address.
New factor: Non-store write suppression.
Stimulus: Present a valid arithmetic-immediate instruction as the current instruction.
Support/witness path: Use the established reset-to-zero fetch setup; no register initialization or support instruction is required.
Public observations: Observe data_write = '0' while the non-store instruction is current.
Forbidden: Do not inspect internal registers, decode controls, or other hierarchy signals.; Do not use unsupported or malformed instruction encodings.; Do not assert data-bus values that have no architectural meaning for this instruction.

## Publica — incremento 4

Behavior: A byte store exposes the unmasked effective byte address rs1 + imm_s.
Coverage gap: Store effective byte address preserves its low address bits instead of masking them.
Prerequisites: Reset establishes the initial fetch address.; A completed sequential instruction advances the fetch address.; A byte-store instruction asserts data_write.
New factor: Unmasked effective byte address
Stimulus: Use a byte store with x0 as its base and a nonzero immediate that sets a low address bit.
Support/witness path: Support: reset, then complete the shortest legal sequential instruction needed to reach the store. Observe the store transaction on the public data interface; do not count instruction sequencing or store enable as new coverage.
Public observations: During the store instruction, data_write is asserted to identify the transaction.; data_addr equals the effective byte address, including the set low address bit.
Forbidden: Do not inspect internal registers, PC signals, decoder outputs, or other hierarchy.; Do not add another focal behavior such as payload routing, width selection, or register writeback.; Do not use an illegal or unsupported instruction encoding.

## Publica — incremento 4

Behavior: During reset, data_write remains deasserted even when the current instruction is a valid store.
Coverage gap: Reset suppresses a store that would otherwise assert data_write.
Prerequisites: Reset is publicly observable through instr_addr.; A valid store can assert data_write outside reset.
New factor: Reset suppression of store writes.
Stimulus: Present a legal store instruction while reset is asserted.
Support/witness path: Use the existing reset-address witness and valid-store write-enable witness as support; do not count either as newly covered.
Public observations: data_write is deasserted while reset is asserted.
Forbidden: Do not inspect internal state or signals.; Do not require a memory commit or assign architectural meaning to other data-bus outputs during reset.

