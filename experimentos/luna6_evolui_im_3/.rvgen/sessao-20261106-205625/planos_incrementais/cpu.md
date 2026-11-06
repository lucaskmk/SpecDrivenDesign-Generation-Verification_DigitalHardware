## Publica — incremento 6

Behavior: A zero-offset JAL to x0 leaves the fetch address unchanged on successive instruction completions.
Coverage gap: JAL x0, 0 self-loop
Prerequisites: Asynchronous reset establishes the fetch address at zero.; Sequential instruction completion already demonstrates that the fetch address is publicly observable and advances.
New factor: Zero-offset JAL preserves the fetch address.
Stimulus: A legal program whose current instruction is a labeled `jal x0, halt` self-loop.
Support/witness path: Support: use the reset-established fetch address; no register setup is needed. Do not count reset behavior as new coverage.
Public observations: Observe `instr_addr` at the self-loop instruction address and verify it remains there across successive completions.
Forbidden: Do not inspect internal PC or next-PC signals.; Do not require register-file or component internals.; Do not add assertions for link values or unrelated data-bus behavior.

## Publica — incremento 7

Behavior: Select byte width for a valid byte store.
Coverage gap: Byte stores must select the byte access width on data_width; the existing byte-store witness checks only data_write.
Prerequisites: A valid store asserts data_write, already witnessed.; Reset permits the store instruction to execute, already witnessed.
New factor: Byte-store width selection.
Stimulus: Execute a legal byte-store instruction using x0 as the source register.
Support/witness path: None required; the store instruction directly exposes its access width on the public bus.
Public observations: During the byte-store instruction, data_width is 00.
Forbidden: Do not inspect internal registers, decoder controls, or hierarchy.; Do not assert store payload or effective-address behavior as newly covered.

## Publica — incremento 8

Behavior: A valid SH instruction selects halfword data width.
Coverage gap: Halfword-store width selection (SH) has no public-port witness.
Prerequisites: Reset and sequential instruction execution are witnessed.; SB already witnesses store decoding and byte-width selection.
New factor: SH selects halfword width.
Stimulus: Execute a legal RV32IM halfword-store instruction.
Support/witness path: No additional support sequence is needed; observe the data bus during the SH instruction.
Public observations: data_write is 1.; data_width is 0x1.
Forbidden: Do not inspect internal signals or require a memory instance.; Do not add store address or payload as focal behaviors.; Do not use illegal or malformed instruction encodings.

## Publica — incremento 9

Behavior: A valid SW asserts data_write and selects word width.
Coverage gap: SW store access-width selection has no public-port witness.
Prerequisites: Valid store write-enable behavior is witnessed by SB and SH cases.; Store width selection is witnessed for byte and halfword stores.
New factor: Word-width store selection.
Stimulus: A legal SW instruction using x0 as its base and source.
Support/witness path: None.
Public observations: data_write is asserted for the SW instruction.; data_width selects word access.
Forbidden: Do not inspect internal signals or require implementation internals.; Do not use unsupported or malformed instruction encodings.; Do not claim coverage of store payload, address generation, or memory commit.

