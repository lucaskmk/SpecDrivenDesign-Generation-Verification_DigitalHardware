## Publica — incremento 1

Behavior: A read of the selected destination returns its old value before an enabled write is accepted and its new value afterward.
Coverage gap: An enabled write to a writable register takes effect only at the write-acceptance boundary; the current suite observes only x0 during reset.
Prerequisites: A known prior value for a writable register.; A public read of that register.
New factor: Enabled writes become visible only when accepted.
Stimulus: A writable register selected for reading while an enabled write requests a distinct value, with the prior and updated values distinguished across the write-acceptance boundary.
Support/witness path: Use asynchronous reset to establish the selected writable register at zero and observe zero through a read port. Treat this only as setup, not as new reset coverage.
Public observations: The selected read output retains the established prior value before write acceptance.; The selected read output reports the requested value after write acceptance.
Forbidden: Do not inspect register-file internals.; Do not count the reset setup as newly covered behavior.; Do not enumerate registers or repeat the same write scenario with different literals.

## Publica — incremento 2

Behavior: Disabled write requests do not modify register state.
Coverage gap: A rising-edge write request with write_enable='0' leaves the selected register unchanged.
Prerequisites: The passing suite demonstrates that an enabled write can initialize a writable register and that its value is observable on read_data1.
New factor: write_enable='0' suppresses a write.
Stimulus: A previously initialized writable register is selected for reading while a disabled write request targets it with a different value.
Support/witness path: Use the already passing enabled-write scenario to establish a known value in a writable register. Treat that initialization only as support for this case.
Public observations: The selected register reads as its established value after the disabled request is sampled; it does not read as the requested value.
Forbidden: Do not require internal state access, enumerate registers, or count the support initialization as new coverage.

## Publica — incremento 3

Behavior: Writes to x0 are ignored.
Coverage gap: An enabled write targeting x0 is ignored; the existing x0 witness checks only its reset value.
Prerequisites: The existing reset and writable-register write-timing cases provide public-port setup and timing witnesses.; No initialization of a nonzero register is needed to observe this behavior.
New factor: Write immunity of x0.
Stimulus: After reset release, request an enabled write of a nonzero value to x0, then select x0 for public read.
Support/witness path: Support: use the established reset-release and write-acceptance setup. Assert only that x0 remains zero after the request; do not count reset release or write timing as new coverage.
Public observations: A read of x0 remains zero after the enabled write request is accepted.
Forbidden: Do not inspect internal register-array state.; Do not treat the reset-only x0 read as evidence that writes to x0 are ignored.; Do not add unrelated register-selection, read-port-independence, or reset-priority checks to this case.

## Publica — incremento 4

Behavior: A read output reflects a newly selected register without waiting for a clock edge.
Coverage gap: Asynchronous read-address selection
Prerequisites: A nonzero register can be initialized by an accepted write; this has a passing public-port witness.
New factor: Asynchronous response to a read-address change
Stimulus: Select a known nonzero register on a read port, then select a different register while no write is accepted.
Support/witness path: Support: initialize the nonzero register with an enabled write, using the already-witnessed write behavior. Focal witness: observe the read port after changing its address.
Public observations: The read output reports the selected register's value after the address change, without a clock edge.; The observation uses only declared ports.
Forbidden: Do not count the support write as newly covered behavior.; Do not require internal signals or exhaustive address enumeration.

