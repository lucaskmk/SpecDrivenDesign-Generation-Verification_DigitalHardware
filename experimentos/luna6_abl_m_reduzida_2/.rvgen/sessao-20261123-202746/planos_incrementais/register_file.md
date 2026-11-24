## Publica — incremento 1

Behavior: A write to x0 has no effect, and both read ports return zero for x0.
Coverage gap: x0 ignores writes and reads as zero
Prerequisites: none
New factor: x0 ignores writes
Stimulus: With reset deasserted, attempt a write of nonzero data to x0 and select x0 on both read ports.
Support/witness path: No separate support sequence is needed; the attempted x0 write is the focal stimulus.
Public observations: Both asynchronous read outputs are zero after the attempted write.
Forbidden: Do not inspect internal state or require a successful write to a nonzero register.

## Publica — incremento 2

Behavior: A committed write to one nonzero destination becomes observable through an asynchronous read.
Coverage gap: A permitted write to a nonzero register stores the supplied value exactly.
Prerequisites: Reset and zero-valued read outputs have a public-port witness.; Writes to x0 are ignored.
New factor: Writing a nonzero register
Stimulus: Write a representative value to one nonzero register and select that register on one read port.
Support/witness path: Use reset as setup, then establish the nonzero register value with the permitted write. Treat reset and setup as support, not newly covered behavior.
Public observations: The selected read output matches the value supplied for the write.
Forbidden: Do not inspect implementation internals.; Do not require enumeration of registers or values.; Do not claim coverage of write timing, write inhibition, read-port independence, or reset clearing previously written state.

## Publica — incremento 3

Behavior: A read output reflects its selected register when the address changes, without a clock transition.
Coverage gap: An asynchronous read-address change selecting a previously written nonzero register
Prerequisites: A permitted write can establish a known value in a nonzero register; this already has a public-port witness.; x0 reads as zero; this already has a public-port witness.
New factor: Asynchronous read-address selection
Stimulus: Use one read port, initially selecting x0, then select a nonzero register with a previously established value while no write is being committed.
Support/witness path: Support: use the public write interface to establish a known value in one nonzero register. Then use the public read-address and read-data ports to observe the address selection.
Public observations: After the address changes, the selected read output equals the established register value without a clock transition.
Forbidden: Do not inspect or require implementation internals.; Do not count the supporting write as newly covered behavior.; Do not require exhaustive register-address coverage.

## Publica — incremento 4

Behavior: rs2_data independently reflects the register selected by rs2_addr without changing the value selected by rs1_addr.
Coverage gap: Independent nonzero selection by the second asynchronous read port while the first port remains fixed.
Prerequisites: A passing witness establishes that a representative nonzero register can be written and read through rs1_data.
New factor: Nonzero selection through the second read port.
Stimulus: Use a representative written nonzero register as the rs2_addr selection while rs1_addr remains fixed at x0; vary only rs2_addr asynchronously.
Support/witness path: Support: write a known value to a representative nonzero register. Then select x0 through rs1_addr and that written register through rs2_addr.
Public observations: Observe rs1_data remains zero and rs2_data reflects the written value after the rs2_addr change, without requiring a clock transition for the read.
Forbidden: Do not inspect hierarchy or require internals. Do not enumerate addresses or add unrelated assertions.

