## Publica — incremento 6

Behavior: A valid byte store selects the byte width on the public data bus.
Coverage gap: SB access-width selection
Prerequisites: The existing suite witnesses that an SB instruction asserts data_write.
New factor: Byte-store width selection
Stimulus: Use a valid byte-store instruction with zero-valued source registers.
Support/witness path: No support sequence is needed; the store can use x0 as both base and data source.
Public observations: data_write is asserted for the store.; data_width identifies a byte access.
Forbidden: Do not inspect internal signals or register-file state.; Do not make payload routing or effective-address calculation additional focal behaviors.

## Publica — incremento 7

Behavior: A valid SH asserts the store interface with halfword width.
Coverage gap: Halfword store access width is not yet witnessed; the passing store-width witness covers only byte stores.
Prerequisites: Reset exposes the initial instruction address.; A valid store can assert data_write outside reset.
New factor: Halfword store width
Stimulus: Execute a legal SH instruction using x0 as the base and source, with zero offset.
Support/witness path: None required.
Public observations: data_write is asserted for the SH instruction.; data_width identifies a halfword access.
Forbidden: Do not inspect internal signals or registers.; Do not claim evidence for store address calculation or payload routing.

## Publica — incremento 8

Behavior: A valid SW asserts data_write and selects word width.
Coverage gap: SW word-width selection has no public-port witness; existing store witnesses cover SB and SH.
Prerequisites: Reset exposes PC zero.; SB and SH witnesses establish store write-enable behavior and byte/halfword width selection.
New factor: Word access width selection for SW.
Stimulus: A legal SW using x0 as its base and source with a zero offset.
Support/witness path: None required; x0 supplies the architecturally defined zero values.
Public observations: data_write is asserted.; data_width selects word access.
Forbidden: Do not inspect internal signals or register-file state.; Do not claim store payload routing, address generation, or memory commit behavior from this case.

## Publica — incremento 9

Behavior: A store's data_addr equals rs1 plus its S immediate, with low address bits preserved.
Coverage gap: S-immediate effective byte-address generation with a nonzero offset
Prerequisites: Reset exposes the instruction address at zero.; A valid SB store is recognized on the public data interface.
New factor: Nonzero S-immediate effective address
Stimulus: Use a legal byte-store instruction with x0 as the base and a nonzero S immediate whose byte address is naturally aligned for a byte access.
Support/witness path: None; x0 supplies the base without prior state, and the active store exposes the effective address directly.
Public observations: While the store instruction is current, data_addr equals x0 plus its S immediate, including the immediate's low address bits.
Forbidden: Do not inspect internal signals or registers.; Do not assert unrelated payload, memory-commit, or control-flow behavior.

