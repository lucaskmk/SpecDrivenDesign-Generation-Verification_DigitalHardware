## Publica — incremento 1

Behavior: The PC advances to the next sequential instruction when no control transfer is taken.
Coverage gap: Sequential PC increment after a completed instruction
Prerequisites: Reset establishes the initial PC at zero; this is witnessed by the passing reset test.
New factor: Sequential PC increment
Stimulus: A legal no-op arithmetic instruction at a sequential fetch address.
Support/witness path: No additional support sequence is needed; the existing reset test establishes the starting PC.
Public observations: Observe instr_addr at consecutive instruction fetches and confirm sequential advancement.
Forbidden: Do not inspect PC or other internal signals.; Do not claim reset behavior as newly covered.

## Publica — incremento 2

Behavior: Reset prevents a rising edge from advancing the PC.
Coverage gap: The PC remains at zero across a rising clock edge while reset is asserted.
Prerequisites: Reset assertion sets instr_addr to zero.
New factor: PC hold across a rising edge during reset.
Stimulus: Present a legal ADDI instruction accepted by assemble_rv32im while reset remains asserted across a rising edge.
Support/witness path: Use the existing asynchronous-reset witness to establish that instr_addr is zero before checking the reset-held edge behavior.
Public observations: Observe instr_addr through the declared port and require it to remain zero across the edge.
Forbidden: Do not inspect internal state or require a register-file witness.; Do not claim that register writes or memory effects are suppressed based on this case.

## Publica — incremento 3

Behavior: A valid JAL x0, 0 leaves instr_addr at the same address across repeated executions.
Coverage gap: JAL self-loop holds the current PC across successive instruction commits
Prerequisites: Asynchronous reset places the PC at zero.; Sequential fetch advances by four.
New factor: JAL self-loop PC hold
Stimulus: Use a legal assembly program whose current instruction is a self-targeting JAL to x0.
Support/witness path: No support sequence is needed; the PC behavior is directly observable through instr_addr.
Public observations: instr_addr remains at the JAL instruction address during repeated execution.
Forbidden: Do not inspect internal PC or jump-control signals.; Do not count reset or sequential-fetch behavior as newly covered.

## Publica — incremento 4

Behavior: Releasing asynchronous reset alone does not advance the PC.
Coverage gap: PC stability when reset is deasserted without an intervening active clock transition
Prerequisites: Asynchronous reset establishes the reset PC, witnessed by the passing reset tests.
New factor: PC stability on reset release
Stimulus: Reset-release stability: establish the reset PC, then release reset while no active clock transition occurs.
Support/witness path: Use the existing public instr_addr observation during asserted reset to establish the starting PC; this is support and does not count as new coverage.
Public observations: Compare instr_addr after reset release with its value immediately before release; require it to remain unchanged until execution resumes.
Forbidden: Do not inspect internal PC or control signals.; Do not require a register or memory model.; Do not count the reset-to-zero observation as new coverage.

