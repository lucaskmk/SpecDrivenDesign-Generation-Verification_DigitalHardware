## Publica — incremento 1

Behavior: After reset has cleared the registers, deasserting reset alone leaves their values unchanged.
Coverage gap: Deasserting reset without a clock does not change the cleared register state.
Prerequisites: The passing suite witnesses zero outputs at nonzero read addresses while reset is asserted.
New factor: State preservation on reset deassertion without a clock.
Stimulus: A reset-cleared register file with reset deasserted and both asynchronous read ports selecting nonzero registers.
Support/witness path: Support: assert reset with nonzero read addresses and allow asynchronous settling to establish the cleared state. Focal witness: deassert reset without a clock and observe the read outputs.
Public observations: Both read outputs remain 0x00000000 after reset is deasserted.
Forbidden: Do not rely on register values before reset.; Do not inspect implementation internals.

## Publica — incremento 2

Behavior: A write to a nonzero destination takes effect on the rising edge when writing is enabled.
Coverage gap: An enabled write to a nonzero register stores the supplied value.
Prerequisites: Asynchronous reset clears registers and produces zero read outputs.; Reset deassertion without a clock edge preserves the cleared values.
New factor: Enabled write to a nonzero register
Stimulus: Write a nonzero value to one nonzero destination while that destination is selected on a read port; use a value distinct from the destination's reset value.
Support/witness path: Support: rely on the already witnessed reset behavior to establish the destination's initial value as zero. Public witness: observe the selected read output before and after the enabled write.
Public observations: The selected read output is zero before the write takes effect.; After the write takes effect, the selected read output equals the supplied write data.
Forbidden: Do not claim asynchronous read-address selection, write-disable behavior, x0 write suppression, or retention of other registers as newly covered.; Do not inspect internal registers or require exhaustive address enumeration.

## Publica — incremento 3

Behavior: A write with rd_write low does not change the selected register.
Coverage gap: A nonzero register is not shown to retain its value when a write is disabled.
Prerequisites: The suite has a passing witness that an enabled write updates a selected nonzero register.
New factor: Write suppression when rd_write is low.
Stimulus: Use a nonzero destination with a known stored value, then present a different value for that destination with writing disabled.
Support/witness path: As support, establish the destination's known value using the already-witnessed reset and enabled-write behavior. The disabled-write scenario is the sole focal behavior; do not count the setup write as new coverage.
Public observations: Read the selected destination through a declared read port before and after the disabled-write transaction.; The observed value remains the previously stored value.
Forbidden: Do not inspect implementation internals.; Do not require exhaustive register-address coverage.

## Publica — incremento 4

Behavior: An enabled write addressed to x0 leaves x0 reading as zero.
Coverage gap: Enabled writes to x0 are ignored, even when rd_data is nonzero.
Prerequisites: Reset-established known state; Enabled-write timing, already witnessed
New factor: Write suppression for destination x0
Stimulus: An enabled write with nonzero data addressed to x0, with both read ports selecting x0.
Support/witness path: Support: use the already-witnessed reset behavior to establish known state. No additional support transaction is needed; the enabled write to x0 is the focal stimulus.
Public observations: Both public read outputs are zero after the attempted write.
Forbidden: Do not inspect implementation internals.; Do not require exhaustive register-address enumeration.

