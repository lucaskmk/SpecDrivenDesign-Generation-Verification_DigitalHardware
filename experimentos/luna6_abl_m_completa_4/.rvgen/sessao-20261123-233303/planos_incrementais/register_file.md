## Publica — incremento 1

Behavior: Reset deassertion without an intervening write preserves the cleared values.
Coverage gap: After asynchronous reset is deasserted without a clock edge, the cleared register values remain zero.
Prerequisites: An asynchronous reset clear, already witnessed by the passing suite.
New factor: Retention of cleared values after reset deassertion.
Stimulus: With reset asserted and nonzero read selections, deassert reset while the clock remains steady and before any write.
Support/witness path: Use the existing asynchronous-reset assertion scenario to establish cleared register state; do not count that clear as new coverage.
Public observations: Both read outputs remain zero after reset is deasserted.
Forbidden: Do not require internal state or hierarchy access.; Do not use a clock edge or a write in the focal scenario.

## Publica — incremento 2

Behavior: Writes to x0 have no effect.
Coverage gap: An enabled write targeting x0 is ignored while reset is inactive.
Prerequisites: The passing suite establishes reset assertion and that cleared values persist after reset deassertion.; The declared public interface provides an x0 read selection and an enabled write transaction.
New factor: Ignoring an enabled write to x0
Stimulus: Attempt an enabled write to x0 with a nonzero data pattern while reset is inactive.
Support/witness path: No separate support sequence is required; use a public read of x0 to witness the attempted write's effect.
Public observations: The public read output selecting x0 remains zero after the attempted write.
Forbidden: Do not require internal register-file state or hierarchy.; Do not claim that nonzero-register writes, write timing, or read-port independence are covered by this case.

## Publica — incremento 3

Behavior: A write to a nonzero destination changes its stored value only at the rising edge.
Coverage gap: An enabled write to a nonzero register has no public-port witness showing that it commits only on a rising edge.
Prerequisites: Reset establishes a known zero value in the destination.; The declared clock, write, and read ports provide the necessary public stimulus and observation.
New factor: Rising-edge commit of an enabled nonzero-register write.
Stimulus: Present a distinctive value for an enabled write to a nonzero register initialized to zero, with that register selected on both read ports.
Support/witness path: Use the already witnessed reset-cleared state; no additional support sequence is needed.
Public observations: Before the qualifying rising edge, both read ports still report the prior zero value.; After the qualifying rising edge, both read ports report the presented write value.
Forbidden: Do not inspect implementation internals.; Do not add a disabled-write case or other independent behavior to this case.

## Publica — incremento 4

Behavior: With reset inactive, read_data1 asynchronously reflects the register selected by read_addr1.
Coverage gap: Asynchronous read-address selection on read port 1: changing its selected address must change its output without a clock edge.
Prerequisites: A qualifying nonzero-register write, already witnessed by the passing suite.; A known zero value at x0, already witnessed by the passing suite.
New factor: Asynchronous read-address selection on read port 1.
Stimulus: A populated nonzero register and x0 are selected successively at read port 1, changing only read_addr1 while read port 2 remains fixed.
Support/witness path: Use the already-witnessed qualifying write behavior to establish a nonzero value in a register. Treat that write only as support; the focal evidence is the subsequent address selection.
Public observations: read_data1 reflects the populated register when read_addr1 selects it.; read_data1 reflects zero when read_addr1 selects x0, without an intervening clock edge.
Forbidden: Do not inspect implementation internals.; Do not count the support write as newly covered behavior.; Do not require a sweep of every register address.

