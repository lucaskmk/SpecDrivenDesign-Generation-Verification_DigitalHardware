## Publica — incremento 1

Behavior: x0 remains zero despite an enabled write request with nonzero write data.
Coverage gap: An enabled write to x0 has no effect; the passing suite selects x0 on one read port but does not assert its output or attempt a write.
Prerequisites: none
New factor: Write protection for x0.
Stimulus: Select x0 on both read ports while requesting an enabled write of a nonzero value to x0.
Support/witness path: No support sequence is needed; x0 requires no initialization.
Public observations: Both read outputs are zero while x0 is selected.; Both read outputs remain zero after the attempted write.
Forbidden: Do not inspect implementation internals.; Do not assume or require any undeclared ports.

## Publica — incremento 2

Behavior: Synchronous write to a nonzero register
Coverage gap: A qualifying write to a nonzero register stores the requested 32-bit value.
Prerequisites: Reset is inactive.; A representative nonzero register address and a 32-bit write value are available.
New factor: A qualifying write stores its value in a nonzero register.
Stimulus: Request an enabled write of a representative 32-bit pattern to one nonzero register while reset is inactive.
Support/witness path: No separate support sequence is needed; observe the selected register through a public read port after the write commits.
Public observations: The read port selecting the written address returns the requested 32-bit value.
Forbidden: Do not inspect internal register storage.; Do not count reset, x0 behavior, or read routing as newly covered.

## Publica — incremento 3

Behavior: A read matching a pending write address returns the pre-write value until the qualifying rising edge.
Coverage gap: A pending write must not change the selected register’s read value before the qualifying rising edge.
Prerequisites: The existing suite demonstrates reset and a synchronous write to a nonzero register.
New factor: No write-through before the rising edge.
Stimulus: Request a write of a distinguishable nonzero value to a nonzero register known to contain zero, while reading that register before any qualifying rising edge.
Support/witness path: Use reset to establish the register’s known zero value; the reset and synchronous-write behaviors are support only.
Public observations: Before the qualifying rising edge, the selected read output remains zero.
Forbidden: Do not inspect internal registers or require hierarchy access.; Do not claim the support reset or eventual write as newly covered behavior.; Do not require an instruction encoding or any behavior outside the register_file public interface.

## Publica — incremento 4

Behavior: Writes are suppressed when write_enable is low.
Coverage gap: A write request with write_enable low does not change a nonzero register across a rising edge.
Prerequisites: A nonzero register can be initialized and read through the public interface.
New factor: Write-enable suppression
Stimulus: Request a write with write_enable low to a nonzero register that already contains a distinguishable value.
Support/witness path: Initialize a representative nonzero register with an enabled write and establish its stored value through a public read. Treat this initialization as support, not new coverage.
Public observations: The register reads as its initialized value before and after the disabled write request spans a rising edge.
Forbidden: Do not inspect implementation internals.; Do not claim the support initialization as newly covered behavior.; Do not add unrelated address-routing, reset, data-pattern, or edge-timing cases.

