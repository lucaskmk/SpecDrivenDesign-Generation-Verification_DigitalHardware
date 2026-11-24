## Publica — incremento 1

Behavior: With reset deasserted, completing a legal non-control instruction advances instr_addr from the current PC to the next sequential address.
Coverage gap: Sequential PC advancement by four after a non-control instruction
Prerequisites: Asynchronous reset establishes the current PC as zero; the passing suite witnesses this.
New factor: Sequential PC advancement
Stimulus: Present a legal non-control instruction at the current fetch address and observe the fetch address across its completion.
Support/witness path: None.
Public observations: instr_addr identifies the current instruction before completion.; instr_addr identifies the sequential instruction afterward.
Forbidden: Internal state or hierarchy.; Claims about the instruction's arithmetic result or register writeback.; Additional control-flow or data-memory behavior.

## Publica — incremento 2

Behavior: A legal non-memory instruction drives data_write low, data_addr and data_write_data to zero, and data_width to the word default.
Coverage gap: Non-memory instruction bus defaults
Prerequisites: Reset establishes the instruction address at zero; this already has a public-port witness.; A legal non-control instruction can be presented; ADDI is already used by the passing suite.
New factor: Non-memory bus defaults
Stimulus: Present a legal immediate arithmetic instruction and check its public data-bus outputs.
Support/witness path: No support sequence is needed; the bus defaults are directly observable while the instruction is presented.
Public observations: data_write is low.; data_addr is zero.; data_write_data is zero.; data_width indicates a word.
Forbidden: Do not inspect CPU internals or require a register-file result.; Do not claim coverage of instruction results, register state, or additional PC behavior from this case.

## Publica — incremento 3

Behavior: A store instruction must not request an external write while reset is asserted.
Coverage gap: Reset-time suppression of a valid store; the passing reset witness does not present a store instruction.
Prerequisites: Reset asserted; A legal store instruction supplied
New factor: Store suppression during reset
Stimulus: A legal word store at the reset address while reset is asserted.
Support/witness path: No support sequence is needed; the public data_write output directly witnesses the behavior.
Public observations: data_write is low
Forbidden: Internal signals or hierarchy; Unsupported, reserved, or malformed instruction encodings; Claims about register state or RAM contents

## Publica — incremento 4

Behavior: A legal JAL to its own address keeps instr_addr at that address across successive instruction completions.
Coverage gap: JAL x0, 0 self-loop PC routing
Prerequisites: Reset establishes the starting PC at zero; this already has a public-port witness.; The instruction address is publicly observable; sequential PC behavior already has a witness.
New factor: JAL self-loop PC routing
Stimulus: Present a legal JAL-to-self instruction with x0 as its destination at the reset address.
Support/witness path: Support: use the already-witnessed reset behavior to establish the starting address. Focal witness: observe instr_addr for the legal JAL-to-self instruction across successive instruction completions.
Public observations: instr_addr remains at the self-loop address across successive completions.
Forbidden: Do not inspect PC or any other internal signal through hierarchy.; Do not require register-file state or claim to test the JAL link value.; Do not require RAM behavior or an external data transaction.

