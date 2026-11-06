## Publica — incremento 1

Behavior: A recognized word load returns the complete data_read_data value as load_result.
Coverage gap: LW full-word load result
Prerequisites: The passing suite already uses a recognized word-load instruction and witnesses address pass-through.
New factor: Full-word load result pass-through
Stimulus: A legal word-load instruction with an aligned effective address and a non-symmetric read word.
Support/witness path: None; the load result is directly observable through the public load_result port.
Public observations: load_result equals the complete data_read_data value.
Forbidden: Do not require implementation internals.; Do not use unsupported, reserved, illegal, or malformed instruction encodings.

## Publica — incremento 2

Behavior: data_addr equals effective_address unchanged for an unsupported instruction.
Coverage gap: Address pass-through for an unsupported load/store instruction class
Prerequisites: A passing address pass-through witness for a recognized load.; Use a legal non-memory instruction accepted by assemble_rv32im.
New factor: Unsupported instruction class
Stimulus: Apply a legal non-memory instruction, such as an ADDI, with a distinct effective address ending in the same offset as the existing load address witness. Use distinct values on the other inputs.
Support/witness path: 
Public observations: Observe that data_addr exactly equals effective_address.
Forbidden: Do not use an illegal or unallocated instruction encoding.; Do not require internal signals.; Do not count unsupported-instruction defaults or other output behavior as covered by this case.

## Publica — incremento 3

Behavior: Unsupported instructions leave data_write low and produce zero data_write_data and load_result, with data_width set to word.
Coverage gap: Unsupported-opcode fallback outputs are not yet witnessed; the existing unsupported-instruction case checks only address pass-through.
Prerequisites: A legal unsupported non-memory instruction is already witnessed; the component is combinational and needs no state setup.
New factor: Unsupported-instruction output defaults
Stimulus: Apply a legal non-memory RV32IM instruction with nonzero store-data and read-data inputs; observe the unsupported-instruction outputs.
Support/witness path: None required. The existing legal ADDI witness establishes the unsupported-instruction class; do not count address pass-through as new coverage.
Public observations: data_write is low; data_write_data is zero; load_result is zero; data_width is word
Forbidden: Reserved, illegal, unallocated, or malformed instruction encodings; Internal signals or hierarchy; Clock, reset, or state assumptions

## Publica — incremento 4

Behavior: For a recognized store, data_write_data equals the complete store_data_in value.
Coverage gap: Recognized-store data pass-through
Prerequisites: None; a legal SB instruction and directly driven public inputs suffice.
New factor: Recognized-store data pass-through
Stimulus: Use a legal SB instruction with a nonzero asymmetric store-data value, and observe the enabled store's output data.
Support/witness path: None; the combinational input and output are directly observable through public ports.
Public observations: data_write is asserted.; data_write_data equals the full store_data_in value.
Forbidden: Do not inspect internal signals or require implementation details.; Do not assert additional behaviors such as address pass-through or store width as focal claims.

