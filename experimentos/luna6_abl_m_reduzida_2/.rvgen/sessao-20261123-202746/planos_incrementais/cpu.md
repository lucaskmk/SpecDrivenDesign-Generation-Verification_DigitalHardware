## Publica — incremento 1

Behavior: Non-store data_write default
Coverage gap: A non-store instruction keeps data_write low.
Prerequisites: none
New factor: data_write is low for a non-store instruction.
Stimulus: Present a legal arithmetic-immediate instruction while the clock is held low.
Support/witness path: None; the instruction itself is the witness.
Public observations: data_write is low.
Forbidden: Do not inspect internal signals or hierarchy.; Do not claim this witnesses sequential execution or register writeback.

## Publica — incremento 2

Behavior: The current instruction address advances to the next sequential instruction address.
Coverage gap: Sequential PC advancement by four after a non-control-flow instruction
Prerequisites: Reset establishes the instruction address at zero.; A legal ADDI instruction is already used by the suite.
New factor: Sequential PC advancement
Stimulus: Use a legal ADDI instruction at the reset vector and observe the sequential fetch address.
Support/witness path: No additional support sequence is needed; reset-to-zero and legal ADDI stimulus already have witnesses.
Public observations: instr_addr identifies the current instruction before it completes.; After the ADDI completes, instr_addr identifies the next sequential instruction address, PC + 4.
Forbidden: Do not inspect internal PC or other hierarchy signals.; Do not claim this case covers register writeback or other instruction semantics.

## Publica — incremento 3

Behavior: A supported SB instruction presents a byte-store transaction on the public data interface.
Coverage gap: Baseline SB byte-store bus presentation has no public-port witness.
Prerequisites: Reset-to-zero PC is already witnessed.; No register setup is needed: x0 supplies the base and store data.
New factor: Byte-store bus presentation.
Stimulus: Present a legal SB instruction using x0 as both base and source, with a zero offset.
Support/witness path: None; the store uses x0 directly.
Public observations: data_write indicates a store.; data_width indicates byte access.; data_addr reflects the effective byte address.; data_write_data reflects the x0 source value.
Forbidden: Do not inspect internal signals or hierarchy.; Do not require observing a RAM-side write or memory contents.; Do not claim this case covers nonzero store-data routing or SH/SW.

## Publica — incremento 4

Behavior: The store effective address includes the encoded S immediate.
Coverage gap: A nonzero positive S-immediate contribution to a store effective address is not yet observed.
Prerequisites: Reset establishes the starting PC.; A legal SB instruction is already witnessed to present a store transaction.
New factor: Positive nonzero S-immediate address contribution.
Stimulus: Use a legal byte store with x0 as its base and a positive nonzero S immediate.
Support/witness path: No additional support sequence is needed; the effective address is directly observable for the focal store.
Public observations: data_addr reflects the positive S immediate.; data_write indicates a store.
Forbidden: Do not inspect internal signals or require implementation details.; Do not add another store-width, data-routing, or register-setup behavior to this case.

