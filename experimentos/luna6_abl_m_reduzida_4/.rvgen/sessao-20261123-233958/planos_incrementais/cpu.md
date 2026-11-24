## Publica — incremento 1

Behavior: The current instruction address advances by four for a sequential instruction.
Coverage gap: Sequential PC advance by four after a legal non-control instruction
Prerequisites: The existing reset test establishes that reset places the PC at zero.
New factor: Sequential PC advance by four
Stimulus: Present a legal non-control instruction at the reset address, with a legal instruction available at the next sequential address.
Support/witness path: Use reset to establish the starting PC, as in the existing test. The non-control instruction is the minimal stimulus needed to expose sequential PC advance; do not count its operation result as additional coverage.
Public observations: Observe instr_addr at the starting address and after the instruction is accepted; it should identify the next sequential address.
Forbidden: Do not inspect internal signals or register-file state.; Do not claim coverage of the instruction's arithmetic result or other instruction classes.

## Publica — incremento 2

Behavior: Non-memory instructions drive data_addr to the zero byte address.
Coverage gap: For a non-memory instruction, data_addr is zero.
Prerequisites: Sequential instruction execution has a passing public-port witness.
New factor: Non-memory data-address default.
Stimulus: Present a legal ordinary arithmetic instruction as the current instruction.
Support/witness path: 
Public observations: Observe data_addr at the zero byte address while the instruction is current.
Forbidden: Accessing DUT internals or hierarchy.; Treating this case as evidence for other non-memory output defaults.

## Publica — incremento 3

Behavior: Reset suppresses store transactions.
Coverage gap: A valid store presented during reset must not assert data_write.
Prerequisites: Reset behavior has an existing public-port witness.; A valid store can be presented without prior register setup by using x0 as both sources.
New factor: Store suppression during reset.
Stimulus: Present a legal store instruction with x0 as its base and data source while reset is asserted.
Support/witness path: None; the store uses x0 operands, so no setup instruction is needed.
Public observations: Check that data_write is low while the store instruction is presented during reset.
Forbidden: Do not inspect internal state or hierarchy.; Do not claim an external memory commit was observed; the public witness is data_write being low.

## Publica — incremento 4

Behavior: A valid store drives data_write high outside reset.
Coverage gap: A valid store asserts data_write when reset is deasserted.
Prerequisites: Reset behavior and sequential instruction advancement have passing public-port witnesses. No register setup is needed to observe data_write.
New factor: Valid-store activation outside reset.
Stimulus: A legal SW using x0 as its source and base, with a nonzero legal S-immediate, while reset is deasserted.
Support/witness path: 
Public observations: data_write is high for the valid store.
Forbidden: Do not inspect internal signals or require implementation internals.; Do not claim coverage of store address, width, data packing, or memory commit.

