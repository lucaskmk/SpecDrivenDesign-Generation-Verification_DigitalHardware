## Publica — incremento 1

Behavior: The current instruction completes at a rising edge and the fetch address advances sequentially by four.
Coverage gap: Sequential PC advancement by four after a non-control instruction
Prerequisites: The existing public-port witness establishes that asynchronous reset sets the fetch address to zero.
New factor: Sequential PC advancement
Stimulus: Supply a legal non-control RV32IM instruction at the reset fetch address.
Support/witness path: Use the already-witnessed reset behavior to establish the initial fetch address. No additional support instruction is needed.
Public observations: Observe the fetch address at the instruction location before completion.; Observe that the fetch address advances sequentially after completion.
Forbidden: Do not inspect internal PC or control signals.; Do not claim register-file or instruction-result behavior from this case.

## Publica — incremento 2

Behavior: A store using x0 as its source presents zero on the public store-data bus.
Coverage gap: Register-file x0 read semantics: using x0 as a source yields zero.
Prerequisites: Asynchronous reset and fetch address zero are covered.; The current instruction can be supplied through instr_data at the public fetch address.
New factor: Reading x0 yields zero.
Stimulus: Supply the legal RV32IM source instruction `sw x0, 0(x0)` at the current fetch address.
Support/witness path: None; the store instruction itself exposes the x0 source value on the public data bus.
Public observations: Observe data_write asserted to establish a store transaction.; Observe data_write_data equal to zero.
Forbidden: Do not inspect or require register-file internals.; Do not claim evidence that writes to x0 are ignored.; Do not assert unspecified bus values or unrelated architectural behavior.

## Publica — incremento 3

Behavior: Expose the specified inactive data-bus defaults during a non-load/store instruction.
Coverage gap: Non-store inactive data-bus defaults: a non-load/store instruction must leave data_write low, data_width at word width, and data_write_data zero.
Prerequisites: The existing suite witnesses asynchronous reset to fetch address zero.; The existing suite witnesses a legal non-control instruction at the current fetch address.
New factor: Non-store inactive data-bus defaults.
Stimulus: Present a legal ADDI instruction at the current fetch address.
Support/witness path: No additional support sequence is needed; the current instruction class and its bus outputs are directly observable through public ports.
Public observations: data_write is low.; data_width is word width.; data_write_data is zero.
Forbidden: Do not inspect internal signals or hierarchy.; Do not assert a value for data_addr, which is unspecified for this instruction.; Do not count register-result or PC behavior as newly covered.

## Publica — incremento 4

Behavior: Reset suppresses store writes.
Coverage gap: A legal store presented while reset is asserted must not assert data_write.
Prerequisites: Asynchronous reset is evidenced by instr_addr being zero.; A legal store is evidenced by data_write being asserted outside reset.
New factor: Store suppression during asserted reset.
Stimulus: Present a legal SW instruction while reset is asserted.
Support/witness path: None; data_write directly witnesses the focal behavior.
Public observations: data_write is low while reset is asserted.
Forbidden: Do not inspect internal state or require a clock edge.; Do not assert unrelated data-bus behavior.

