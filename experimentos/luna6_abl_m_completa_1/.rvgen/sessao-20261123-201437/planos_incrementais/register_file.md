## Publica — incremento 1

Behavior: An enabled write addressed to x0 does not change the zero value returned by reads of x0.
Coverage gap: Enabled writes to x0 are ignored.
Prerequisites: The existing suite witnesses read_data1 returning zero when read_addr1 selects x0.; The declared public interface provides clk, write_enable, write_addr, and write_data.
New factor: An enabled write targeting x0 is ignored.
Stimulus: An enabled write request addressed to x0 with both read ports selecting x0 and a nonzero payload.
Support/witness path: None; the focal write and its readback are directly observable through declared ports.
Public observations: read_data1 remains zero.; read_data2 remains zero.
Forbidden: Do not require internal signals or hierarchy.; Do not count preservation of nonzero registers as covered.; Do not claim write-enable behavior for nonzero destinations is covered.

## Publica — incremento 2

Behavior: An enabled write to a nonzero destination updates that register on a rising edge.
Coverage gap: Enabled write to a nonzero register
Prerequisites: The declared clock, reset, write, and read ports provide the required public interface.; Use reset as support to establish a known-zero destination.
New factor: Enabled write to a nonzero destination
Stimulus: One enabled write of a nonzero data pattern to a representative nonzero destination selected for public reading.
Support/witness path: Use reset to establish the selected destination's zero value, then observe that destination through a read port before and after the write transaction. Treat reset only as support, not as newly covered behavior.
Public observations: The selected destination reads zero before the write takes effect.; The selected destination reads the supplied data after the enabled write takes effect.
Forbidden: Do not require internal signals or hierarchy.; Do not add multiple destinations, data-pattern edge cases, or unrelated reset assertions.; Do not claim asynchronous read selection or other reset semantics as newly covered by this case.

## Publica — incremento 3

Behavior: Each read port asynchronously presents the value selected by its address.
Coverage gap: Asynchronous read selection for a nonzero register: changing a read address updates the corresponding output without a clock edge.
Prerequisites: A representative nonzero register contains a known value.
New factor: Address-driven asynchronous read update
Stimulus: Use a representative nonzero register containing a known value, then select it on a read port after that value has been established.
Support/witness path: Support: establish the register value with an enabled write on a rising edge. Then change the read address and observe the selected value without a clock edge. Do not count the support write as newly covered.
Public observations: The selected read output reflects the established register value after the address changes, without a clock edge.
Forbidden: Do not inspect implementation internals.; Do not treat the support write as new coverage.; Do not add a second read-routing, write-enable, or reset behavior to this case.

## Publica — incremento 4

Behavior: write_enable = 0 suppresses a write
Coverage gap: A disabled write leaves an already initialized nonzero register unchanged.
Prerequisites: A representative nonzero register contains a known marker.; The register can be observed through a declared read port.
New factor: Write suppression when write_enable is low.
Stimulus: A representative nonzero destination containing a marker is presented with a different write value while writes are disabled.
Support/witness path: Support: initialize the destination using the already witnessed enabled write to a nonzero register. Select that destination on a read port to observe its stored value.
Public observations: After the disabled write opportunity, the selected register still returns its original marker.
Forbidden: Do not require internal register-file signals or hierarchy.; Do not count the support initialization as new coverage.; Do not assert unrelated register contents or add another focal behavior.

