## Publica — incremento 1

Behavior: An enabled write to x0 does not change its architectural value; reading x0 still returns zero.
Coverage gap: Writes targeting x0 are discarded
Prerequisites: Reset is inactive for the write transaction.; No nonzero-register initialization is required.
New factor: Discarding writes to x0
Stimulus: An enabled, reset-inactive write transaction targets x0 with a nonzero write value, and x0 is selected for public readback.
Support/witness path: No separate support sequence is needed; the x0 write is the focal transaction, and the public read of x0 is its witness.
Public observations: The read output selecting x0 is zero after the attempted write.
Forbidden: Do not inspect internal register storage.; Do not require writes to other destinations, exhaustive address sweeps, or unrelated timing and reset cases.

## Publica — incremento 2

Behavior: A write to a nonzero destination updates that register with rd_data.
Coverage gap: An enabled write to a nonzero register has no public-port witness.
Prerequisites: The existing asynchronous-reset test observes the selected nonzero register x1 as zero, providing a known prior value.
New factor: Accepted write to a nonzero register.
Stimulus: One enabled write of a nonzero value to a nonzero register, with that register selected for readback.
Support/witness path: Use the already-witnessed reset state to establish the selected register's prior zero value; the write and readback are the focal case.
Public observations: The selected register reads as zero in the established reset state.; The selected register reads as rd_data after the write is accepted.
Forbidden: Do not require or inspect implementation internals.; Do not claim coverage of other registers, write-enable timing edges, or read-port selection behavior from this case.

## Publica — incremento 3

Behavior: rs1_data asynchronously reflects the register selected by rs1_addr.
Coverage gap: Asynchronous read-address selection: changing rs1_addr changes rs1_data without a clock edge.
Prerequisites: An accepted write to a nonzero register followed by readback is already witnessed.; x0 read behavior is already witnessed.
New factor: Asynchronous rs1 address selection
Stimulus: With a nonzero register holding a known value, change rs1_addr between that register and x0 while the clock remains steady.
Support/witness path: Use the already witnessed accepted-write/readback pattern to establish a known nonzero register value. Treat that write and its readback only as support, not as newly covered behavior.
Public observations: After selecting the known nonzero register, rs1_data reflects its known value without a clock edge.; After selecting x0, rs1_data is zero without a clock edge.
Forbidden: Do not inspect or require implementation internals.; Do not require sweeping all register addresses.; Do not count the support write as new evidence.

## Publica — incremento 4

Behavior: rs2_data reflects the register selected by rs2_addr asynchronously, without requiring a clock edge.
Coverage gap: Asynchronous selection through the rs2 read port
Prerequisites: Reset establishes a known zero state.; An accepted write to a nonzero register is publicly witnessed.
New factor: Asynchronous selection through rs2
Stimulus: Select a nonzero register with a publicly established value through rs2_addr while the clock is steady.
Support/witness path: Use the already-witnessed reset and accepted nonzero-register write behavior to establish a known value for the selected register; treat those actions only as support.
Public observations: rs2_data reflects the selected register's established value after propagation, without a clock edge.
Forbidden: Do not require internal signals or hierarchy.; Do not claim rs1 behavior as newly covered.; Do not require exhaustive address enumeration.

