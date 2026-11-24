## Publica — incremento 1

Behavior: The current instruction completes and the next instruction address advances by four.
Coverage gap: Sequential PC advancement by four for an ordinary legal instruction.
Prerequisites: Asynchronous reset establishes instruction address zero; the passing suite witnesses this.
New factor: Sequential PC advancement.
Stimulus: Present a legal no-op instruction and allow it to complete.
Support/witness path: Use reset to establish the starting instruction address, then present the no-op instruction.
Public observations: Observe instr_addr at the starting instruction.; After the instruction completes, observe instr_addr advanced by four.
Forbidden: Do not inspect internal signals or register-file state.; Do not use illegal or reserved instruction encodings.

## Publica — incremento 2

Behavior: The stop-loop jump leaves the PC at the current instruction.
Coverage gap: JAL x0, 0 holds the instruction address across successive completed instructions.
Prerequisites: Reset establishes the fetch address.; An ordinary instruction advances the fetch address by four.
New factor: JAL x0, 0 holds the PC.
Stimulus: A program whose current instruction is the legal stop-loop form JAL x0, 0.
Support/witness path: Use the existing reset-to-zero witness to establish the fetch origin. No additional support instruction is needed.
Public observations: instr_addr remains at the stop-loop instruction address across successive rising edges.
Forbidden: Do not inspect or require internal signals.; Do not assert register or data-bus behavior; those are not needed to witness the focal behavior.; Do not use an illegal or malformed instruction encoding.

## Publica — incremento 3

Behavior: For a non-store instruction, the data bus presents the specified inactive defaults.
Coverage gap: Non-store data-bus defaults during normal execution
Prerequisites: A legal non-store instruction is available; the existing ordinary ADDI case provides a public witness for executing one.
New factor: Non-store data-bus defaults
Stimulus: Present a legal non-store arithmetic instruction with zero-valued source operands while reset is deasserted.
Support/witness path: Reuse the existing ordinary ADDI scenario as support. Observe only the data-bus defaults for this case; do not count its sequential-PC behavior again.
Public observations: Already witnessed: reset exposes an instruction address of zero.; Already witnessed: an ordinary instruction advances the instruction address by four.; Already witnessed: JAL x0, 0 holds the instruction address across successive executions.; New witness: data_write is low, data_addr and data_write_data are zero, and data_width is the word-width default.
Forbidden: Do not inspect internal signals or hierarchy.; Do not require register-file initialization or assert unobservable register values.; Do not count PC advancement as new coverage.

## Publica — incremento 4

Behavior: While reset is active, a valid store instruction must not assert data_write or cause an external memory write.
Coverage gap: Suppression of a valid store request while reset is active
Prerequisites: The existing reset witness establishes that the public reset interface is exercised.; A legal store instruction can be presented through instr_data.
New factor: Reset-time store suppression
Stimulus: Present a legal store instruction while reset is active.
Support/witness path: Use the external memory model to observe whether a write transaction is requested or recorded while the store instruction is presented under reset.
Public observations: data_write remains low.; The external memory model records no store.
Forbidden: Do not inspect internal CPU signals or register-file state.; Do not assert unrelated reset outputs or store address, width, or data behavior.

