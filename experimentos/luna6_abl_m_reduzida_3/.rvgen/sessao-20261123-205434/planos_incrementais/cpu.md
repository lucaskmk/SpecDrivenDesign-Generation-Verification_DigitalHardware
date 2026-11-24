## Publica — incremento 1

Behavior: A legal non-control instruction advances instr_addr by four when executed.
Coverage gap: Ordinary sequential PC advancement
Prerequisites: The reset-established fetch address is publicly observable.
New factor: Sequential PC advancement
Stimulus: A legal ordinary instruction at the reset-established fetch address.
Support/witness path: Use reset to establish the starting fetch address, then supply the legal ordinary instruction.
Public observations: instr_addr identifies the instruction's current address before execution.; After execution, instr_addr identifies the next sequential address.
Forbidden: Do not inspect internal signals or registers.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.

## Publica — incremento 2

Behavior: The current instruction address remains unchanged across a falling edge.
Coverage gap: A falling edge does not advance the PC.
Prerequisites: Reset establishes the initial PC.; An ordinary instruction advances the PC by four on a rising edge.
New factor: Falling-edge non-advancement of the PC.
Stimulus: A legal ordinary sequential instruction at a nonzero current PC, with no control transfer.
Support/witness path: Use the already-covered sequential-PC behavior to establish a nonzero current PC; treat that instruction as support, not new coverage.
Public observations: instr_addr has the same value before and after the falling edge.
Forbidden: Do not inspect or require internal signals.; Do not count sequential PC advancement as newly covered.

## Publica — incremento 3

Behavior: A legal halt-loop jump keeps instr_addr at the same address on successive rising edges.
Coverage gap: JAL x0, 0 holds the current instruction address across rising edges.
Prerequisites: Reset establishes the instruction address.; An ordinary instruction advances the PC by four.
New factor: JAL self-loop holds the PC.
Stimulus: Place a legal JAL-to-self instruction at the current instruction address and execute it on successive rising edges.
Support/witness path: No support sequence is needed; the existing reset and sequential-PC cases establish the starting address.
Public observations: Observe instr_addr before and after each rising edge and require it to remain at the current instruction address.
Forbidden: Do not inspect internal signals or registers.; Do not use an illegal or malformed instruction encoding.

## Publica — incremento 4

Behavior: For a legal non-store instruction, data_write is low during that instruction cycle.
Coverage gap: Non-store instructions drive data_write low.
Prerequisites: The existing reset case establishes the instruction address at reset.; The existing ordinary-instruction case establishes a legal instruction at the current address.
New factor: Non-store data_write deassertion.
Stimulus: Present a legal immediate arithmetic instruction at the current instruction address.
Support/witness path: Use reset and the instruction source to present the legal instruction; these are support only and are not newly covered.
Public observations: Observe that data_write is '0' while the instruction is current.
Forbidden: Do not inspect internal signals or require implementation hierarchy.; Do not assert register results, data addresses, or other data-bus properties for this case.

