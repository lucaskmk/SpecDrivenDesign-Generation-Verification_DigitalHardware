## Publica — incremento 6

Behavior: RV32I ADD selects ordinary ALU writeback with m_enable deasserted.
Coverage gap: A valid non-M instruction has no public-port witness that m_enable is deasserted.
Prerequisites: The passing suite already witnesses ADD’s other control outputs and MUL’s asserted m_enable. It also witnesses ADDI register write with rd=x0, LUI’s ALU selection, and SUB’s other control outputs. None of those tests observes deasserted m_enable.
New factor: Non-M M-result disable
Stimulus: A legal RV32I ADD with a nonzero destination register.
Support/witness path: None; the focal behavior is directly observable at the public m_enable port.
Public observations: Compare the complete decoder output tuple, with m_enable deasserted and ADD’s previously witnessed controls unchanged.
Forbidden: Do not inspect internals, test operand results, or use unsupported instruction encodings.

## Publica — incremento 7

Behavior: A valid register-register SLL selects the SLL ALU operation while retaining the RV32I OP control tuple.
Coverage gap: RV32I OP SLL has no public-port witness for its distinct ALU selection.
Prerequisites: The passing suite already witnesses the complete ADD control tuple, including m_enable, for a valid RV32I OP instruction.
New factor: SLL ALU selection
Stimulus: A legal register-register SLL using the same register indices as the witnessed ADD.
Support/witness path: Use the existing ADD public-port witness as the baseline; the SLL instruction is the focal transaction. No additional support sequence is needed.
Public observations: Compare every declared output with the SLL tuple: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=0, alu_control=0x2, branch_enable=0, jump=0, jalr=0, wb_select=0x0, m_enable=0.
Forbidden: Do not inspect internals, use an illegal encoding, vary register indices, or count the already-witnessed ADD behavior as new coverage.

## Publica — incremento 8

Behavior: SLT selects the signed-less-than ALU control while retaining the RV32I OP control tuple.
Coverage gap: RV32I OP signed-less-than decode has no public-port witness.
Prerequisites: Passing ADD and SLL cases establish the RV32I OP control tuple; the SUB case establishes a distinct OP ALU-control selection.
New factor: SLT ALU-control selection
Stimulus: A legal RV32IM SLT instruction with register operands and a nonzero destination.
Support/witness path: None; the instruction directly exposes the focal decode through public outputs.
Public observations: Compare every declared output after combinational settling: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=0, alu_control=0x3, branch_enable=0, jump=0, jalr=0, wb_select=0x0, m_enable=0.
Forbidden: Do not inspect internals, test an ALU result, use an illegal encoding, or treat different register literals as new evidence.

## Publica — incremento 9

Behavior: A valid SLTU selects the unsigned less-than ALU control while retaining the RV32I OP control tuple.
Coverage gap: RV32I OP unsigned less-than decoding (SLTU)
Prerequisites: The suite already has public-port witnesses for the RV32I OP tuple (ADD) and signed less-than selection (SLT).
New factor: Unsigned less-than ALU selection
Stimulus: A legal SLTU instruction with a nonzero destination and two source registers, accepted by assemble_rv32im.
Support/witness path: No support sequence is needed; the instruction directly exposes its decode through public outputs.
Public observations: Check all ten outputs: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=0, alu_control=0x4, branch_enable=0, jump=0, jalr=0, wb_select=0x0, m_enable=0.
Forbidden: Do not inspect internals, use an illegal encoding, or treat the decoder as computing a comparison result.

