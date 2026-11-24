## Publica — incremento 1

Behavior: Hardwired-zero reads from x0.
Coverage gap: Reads of x0 return zero outside reset, including while a write targets x0.
Prerequisites: none
New factor: Hardwired-zero reads from x0
Stimulus: With reset inactive, select x0 on both asynchronous read ports while an enabled write targets x0 with nonzero data.
Support/witness path: 
Public observations: Both read outputs are zero.
Forbidden: Do not assert anything about nonzero registers or claim that writes to x0 leave them unchanged.; Do not require implementation internals.

## Publica — incremento 2

Behavior: An enabled write to a nonzero destination takes effect synchronously; its prior value is visible before the write takes effect, and the written value is visible afterward.
Coverage gap: Synchronous write to a representative nonzero register: the suite has no public-port witness that an enabled write changes a nonzero register.
Prerequisites: The passing reset test establishes a reset-cleared nonzero register as the prior value.
New factor: Synchronous write to a nonzero register.
Stimulus: A representative nonzero destination is selected on one read port and targeted by an enabled write; a different reset-cleared register is selected on the other read port.
Support/witness path: No additional support sequence is needed; use the reset-cleared state established by the existing reset witness.
Public observations: The destination read output shows its prior reset-cleared value before the write takes effect.; After the write takes effect, the destination read output shows the written value.; The other selected register remains reset-cleared.
Forbidden: Do not inspect or require implementation internals.; Do not claim coverage of disabled writes, reset-time write suppression, or asynchronous reset assertion from this case.

## Publica — incremento 3

Behavior: A disabled write leaves register state unchanged.
Coverage gap: rd_write = '0' prevents a rising clock edge from modifying a register.
Prerequisites: A representative nonzero register can be initialized by an enabled write; this has a passing witness.
New factor: Write inhibition when rd_write is low.
Stimulus: A scenario class in which a register has a known nonzero value, then a write is directed to a different nonzero destination while writing is disabled.
Support/witness path: Support: establish the known value using the already-witnessed enabled-write behavior. Do not count that initialization as new coverage.
Public observations: The initialized register retains its value.; The disabled destination retains its prior value.
Forbidden: Do not require internal state or hierarchy.; Do not claim asynchronous read routing, same-address reads, clearing previously populated registers on asynchronous reset, or ignoring writes during reset as covered by this case.

## Publica — incremento 3

Behavior: Write inhibition when rd_write is low.
Coverage gap: A clocked write attempt with rd_write = '0' must leave an already initialized nonzero register unchanged.
Prerequisites: An enabled write to a nonzero register has a passing public-port witness.; The initialized register's value can be observed through a read port.
New factor: Write inhibition when rd_write is low.
Stimulus: Attempt a disabled write to an already initialized nonzero destination using a distinct payload.
Support/witness path: Support only: initialize a representative nonzero register with an enabled write and establish its value through a public readback.
Public observations: The destination reads as its established value before the disabled write attempt.; The destination still reads as that value after the attempt.
Forbidden: Do not require implementation internals.; Do not count the support write as new coverage.; Do not add unrelated reset, read-routing, or x0 assertions.

## Publica — incremento 4

Behavior: Asserting active-high reset asynchronously clears nonzero registers.
Coverage gap: Asynchronous reset clears a previously nonzero register without waiting for a rising clock edge.
Prerequisites: A synchronous write to a nonzero register is already witnessed.
New factor: Asynchronous clearing of previously written state.
Stimulus: A representative nonzero register holds an established nonzero value when reset is asserted between rising clock edges, with a read port selecting that register.
Support/witness path: Use the already-witnessed enabled write behavior only as support to establish the register's nonzero value; then use the public read output to witness the reset effect. Do not count the support write as new coverage.
Public observations: The selected read output is nonzero before reset assertion.; The selected read output becomes zero while reset is asserted, without waiting for a rising clock edge.
Forbidden: Internal register-array or reset-state inspection.; Treating the support write as newly covered behavior.; Adding write-while-reset or post-reset write behavior as additional focal coverage.

