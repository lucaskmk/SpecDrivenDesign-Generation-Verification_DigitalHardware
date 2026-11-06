## Publica — incremento 6

Behavior: A valid SH selects halfword width on the public data bus.
Coverage gap: Halfword-store access width selection
Prerequisites: Reset establishes the instruction address at zero.; A valid store asserts data_write.
New factor: Halfword-store width selection
Stimulus: Present a legal halfword store using x0 as both base and source.
Support/witness path: Use the existing reset-at-zero setup; x0 requires no register initialization. The existing byte-store witness supports recognizing an active store.
Public observations: data_write is asserted for the halfword store.; data_width selects halfword.
Forbidden: Do not inspect internal signals or registers.; Do not treat the support store-enable behavior as newly covered.; Do not require memory-commit behavior or assert unrelated data-bus values.

## Publica — incremento 7

Behavior: For a valid byte load, data_addr equals rs1 plus the sign-extended I immediate, including nonzero low address bits.
Coverage gap: A load’s effective byte address is exposed on the public data bus without masking its low address bits.
Prerequisites: Existing reset evidence establishes a known fetch address of zero.; The case needs no register initialization because x0 supplies the base.
New factor: Load effective-address generation preserves low address bits.
Stimulus: A valid byte-load instruction using x0 as its base, a nonzero byte offset with nonzero low address bits, and x0 as its destination.
Support/witness path: Support: use the established reset state and present the valid load at the current fetch address. Observe the load’s public data-bus address before instruction completion. Do not count reset or fetch sequencing as newly covered.
Public observations: data_addr equals the byte offset and retains its nonzero low address bits.
Forbidden: Do not inspect internal registers, decode controls, or other hierarchy.; Do not assert load extraction or register writeback; neither is needed to witness this behavior.; Do not use an illegal or unsupported instruction encoding.

## Publica — incremento 8

Behavior: A valid word store asserts data_write and selects word width.
Coverage gap: SW word-store width selection
Prerequisites: Reset establishes the fetch address at zero.; Existing SB and SH witnesses establish store recognition and halfword-width selection.
New factor: Word-store width selection
Stimulus: A valid SW using x0 as its base and source.
Support/witness path: No support sequence is needed; observe the store directly on the public data interface.
Public observations: data_write is asserted.; data_width selects word access.
Forbidden: Do not inspect internal state or require implementation hierarchy.; Do not assert store payload or memory-commit behavior; they are not needed to witness the focal behavior.

## Publica — incremento 9

Behavior: A valid byte load selects byte width on the data interface.
Coverage gap: Load access-size selection for a byte load is not yet observed on the public data_width port.
Prerequisites: Asynchronous reset establishes the fetch address at zero.; A legal byte load and its effective-address behavior already have a passing witness.
New factor: Byte-load access-width selection.
Stimulus: A legal byte-load instruction with an otherwise irrelevant destination.
Support/witness path: No support sequence is needed; the load instruction itself exposes the selected width on the public data interface.
Public observations: data_width indicates byte access.
Forbidden: Do not inspect internal registers, decoder signals, or hierarchy.; Do not assert unrelated load-result, address, write-enable, or reset behavior as newly covered.; Do not use an illegal or unsupported instruction encoding.

