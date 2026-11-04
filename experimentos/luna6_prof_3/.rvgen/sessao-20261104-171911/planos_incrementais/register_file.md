## Publica — incremento 1

Behavior: A qualifying write stores the supplied 32-bit value in the selected nonzero register, observable through a public read port.
Coverage gap: Successful write to a nonzero register
Prerequisites: No prior write behavior is required; establish a known zero baseline using reset and release reset before the focal write.
New factor: Nonzero-register write storage
Stimulus: Use a nonzero destination such as x5 and a nonzero 32-bit value; observe that register through a read port after the write.
Support/witness path: Use reset only to establish a known zero baseline, then release it. Treat the write and its readback as the focal case; do not count reset behavior as newly covered.
Public observations: The selected read port reports the supplied value for x5 after the qualifying write.
Forbidden: Do not inspect internal register storage or other hierarchy.; Do not claim asynchronous read selection, write-enable inhibition, write timing before the qualifying edge, preservation of other registers, or reset priority from this case.

## Publica — incremento 2

Behavior: rs1_data reflects the value selected by rs1_addr without waiting for a clock edge.
Coverage gap: Asynchronous read response to a read-address change
Prerequisites: A passing public-port witness establishes that a nonzero value can be written to x5 and read back.
New factor: Asynchronous read response to address changes
Stimulus: After establishing a nonzero value in x5, vary rs1_addr between x5 and x0 while keeping rs2_addr fixed.
Support/witness path: Use the already-witnessed write behavior to establish a nonzero value in x5. Then observe rs1_data as rs1_addr selects x5 and x0, without a clock edge between address changes. Treat the write only as support, not as newly covered behavior.
Public observations: rs1_data reflects the established x5 value when rs1_addr selects x5.; rs1_data reflects zero when rs1_addr selects x0.
Forbidden: Do not inspect or require internal signals or hierarchy.; Do not claim independent-port behavior, write-enable behavior, reset priority, or preservation as newly covered.; Do not require exhaustive register-address enumeration.

## Publica — incremento 3

Behavior: rs2_data asynchronously reflects the register selected by rs2_addr, independently of rs1_addr
Coverage gap: Asynchronous selection of a nonzero register on the rs2 read port
Prerequisites: Reset-to-zero behavior has a public-port witness.; A qualifying write to a nonzero register and readback has a public-port witness.
New factor: Asynchronous address selection on rs2
Stimulus: Use a representative nonzero register with a known stored value; keep rs1_addr selecting x0 while rs2_addr selects that register.
Support/witness path: Support: establish the known value with a qualifying write to the representative nonzero register. Then select x0 on rs1_addr and the written register on rs2_addr; the setup write is not newly covered.
Public observations: Without a clock edge after changing rs2_addr, rs2_data presents the stored value.; rs1_data continues to present zero for its unchanged x0 selection.
Forbidden: Do not inspect implementation internals.; Do not claim write behavior as newly covered by the support sequence.; Do not add unrelated reset, write-enable, preservation, or register-address cases.

## Publica — incremento 4

Behavior: A write-enabled transaction targeting x0 must leave both asynchronous reads of x0 at zero.
Coverage gap: Writes addressed to x0 have no effect.
Prerequisites: Reset establishes a known register state.; A qualifying write to a nonzero register and asynchronous readback are already witnessed.; Both read ports selecting x0 are already witnessed.
New factor: Write to x0 has no effect.
Stimulus: A write-enabled transaction targeting x0 with a representative nonzero value, followed by selecting x0 on both read ports.
Support/witness path: Use reset to establish a known state. The existing nonzero-register write/readback witness establishes the write path; do not count that support behavior as new coverage.
Public observations: Both read ports report zero for x0 after the attempted write.
Forbidden: Do not inspect internal register storage.; Do not require exhaustive write-data patterns or register-address enumeration.; Do not count reset or ordinary write-path behavior as newly covered.

