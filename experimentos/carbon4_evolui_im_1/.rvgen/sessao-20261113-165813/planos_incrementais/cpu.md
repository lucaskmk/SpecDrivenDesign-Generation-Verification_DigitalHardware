## Publica — incremento 6

Behavior: When rst is deasserted and instr_data presents a valid word-store instruction, cpu combinationally drives the word access-size encoding onto data_width.
Coverage gap: Word-store access-width encoding on data_width (Test strategy 9: store width routing)
Prerequisites: Asynchronous reset places instr_addr at the initial fetch address; A valid word-store instruction outside reset is decoded as an active store asserting data_write
New factor: Word-store access-width encoding on data_width
Stimulus: A minimal legal RV32I word-store program using the architectural zero register for the base address and source data with a zero offset, presented on instr_data during non-reset operation.
Support/witness path: Use asynchronous reset initialization solely as support to establish the initial fetch address on instr_addr before releasing rst to expose the combinational word-store bus outputs.
Public observations: While rst is deasserted with the word-store instruction presented on instr_data at the initial instr_addr, data_width exposes the word access-size code alongside active store qualification on data_write.
Forbidden: Do not read internal hierarchy signals or decoder outputs; Do not bundle nonzero address offsets, prior register writes, or multiple store widths into this case; Do not use illegal, reserved, or malformed instruction encodings

## Publica — incremento 7

Behavior: For a byte-store instruction outside reset, the CPU computes the effective byte address from the base register plus the S-format immediate and drives that unmasked byte address onto data_addr.
Coverage gap: Unmasked store effective byte address generation from a nonzero S-format immediate on data_addr
Prerequisites: Asynchronous reset sets instr_addr to the initial fetch address and holds architectural registers at zero; A byte-store instruction outside reset combinationaly asserts data_write
New factor: Unmasked effective byte address generation on data_addr from a nonzero S-format store offset
Stimulus: Outside reset at the initial program address, present a legal RV32IM byte-store instruction referencing the zero register with a positive nonzero S-format byte offset whose low address bits are nonzero.
Support/witness path: Support: asynchronous reset establishes the initial fetch address with zeroed register state, then releasing reset exposes the byte-store instruction at that fetch address. Witness: public port data_addr directly exposes the combinational effective byte address while data_write confirms the store cycle.
Public observations: instr_addr holds the initial fetch address during reset and immediately after reset release; data_write asserts for the active byte-store instruction; data_addr equals the exact unmasked positive byte offset specified by the S-format immediate
Forbidden: Inspecting internal signals or subcomponents such as immediate generator outputs, ALU signals, or internal effective-address wires; Using misaligned halfword or word stores whose behavior is unspecified; Introducing prior register-writing instructions when the zero register suffices as the base operand; Counting reset behavior or basic store write-enable assertion as newly covered

## Publica — incremento 8

Behavior: When a valid load instruction is presented outside reset, the CPU computes the effective byte address by adding rs1 to the sign-extended I-format immediate and combinationally drives that unmasked byte address onto data_addr while keeping data_write deasserted.
Coverage gap: Load effective byte address generation from an I-format immediate offset on data_addr
Prerequisites: Asynchronous reset sets instr_addr to the initial fetch address and releasing reset preserves that fetch address before sequential advancement; Architectural register x0 supplies zero as a base operand and data_addr exposes unmasked byte-level offsets; Non-store instructions keep data_write deasserted when reset is inactive
New factor: Unmasked I-format effective byte address routing on data_addr for a load instruction
Stimulus: A valid RV32IM byte-load instruction using architectural zero register x0 as the base operand with a positive nonzero unaligned I-format byte offset, presented on the instruction bus while reset is inactive at the initial fetch address.
Support/witness path: Use asynchronous reset assertion followed by reset release as minimal support to establish the known initial fetch address so the load instruction is fetched and its combinational address output is directly witnessed on data_addr.
Public observations: instr_addr holds the initial fetch address during reset and after reset release; data_addr combinationally equals the unmasked positive byte offset computed from x0 plus the I-format immediate; data_write remains deasserted while the byte-load instruction is presented
Forbidden: Inspecting internal hierarchy signals or submodules such as imm_i, effective_addr, u_immediate_generator, u_decoder, or u_alu; Using S-format store instructions as the focal stimulus; Bundling load data extraction, register writeback, or multi-instruction sequences into this case; Using reserved, illegal, or malformed encodings not accepted by assemble_rv32im

## Publica — incremento 9

Behavior: When a byte-load instruction with base register x0 and a negative I-type immediate is presented outside reset, the CPU sign-extends the 12-bit immediate to 32 bits and combinationaly drives the resulting unmasked 32-bit effective byte address onto data_addr while keeping data_write low.
Coverage gap: Sign extension of a negative I-type immediate in load effective byte address generation
Prerequisites: Asynchronous reset initializes instr_addr to zero and retains that fetch address upon reset release prior to clock completion; A byte-load instruction with base register x0 and a positive I-type immediate drives the unmasked effective byte address onto data_addr while keeping data_write low
New factor: Negative I-type immediate sign extension in load effective byte address calculation
Stimulus: A single legal RV32I byte-load instruction at the initial fetch address using the architectural zero register as base with a negative signed immediate offset under inactive reset.
Support/witness path: Asynchronous reset assertion followed by reset release establishes the initial fetch address on instr_addr so the byte-load instruction supplied on instr_data directly exposes the sign-extended offset from x0 on data_addr without prior instruction state.
Public observations: instr_addr remains at the initial reset fetch address while the byte-load instruction is presented; data_addr equals the 32-bit sign-extended negative byte offset with upper sign bits set and low byte-offset bits preserved unmasked; data_write remains deasserted for the byte-load instruction
Forbidden: Reading internal hierarchy signals such as imm_i, effective_addr, u_immediate_generator, or u_register_file; Combining register initialization sequences, stores, branches, jumps, or RV32M instructions in the same test; Using raw illegal or reserved instruction encodings not accepted by assemble_rv32im

