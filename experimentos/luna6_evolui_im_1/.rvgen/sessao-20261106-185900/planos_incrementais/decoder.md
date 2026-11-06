## Publica — incremento 6

Behavior: A legal register-register SLL instruction is recognized as a register-writing OP instruction and selects the SLL ALU operation.
Coverage gap: RV32I OP SLL function decoding
Prerequisites: The public-port suite already witnesses the OP class with ADD and SUB.
New factor: SLL ALU-operation selection
Stimulus: Use a legal register-register SLL instruction with representative nonzero register fields.
Support/witness path: None required; the instruction’s controls directly witness the selected operation.
Public observations: Check the complete output tuple: reg_write asserted; mem_write, alu_src_a_pc, alu_src_b_imm, branch_enable, jump, and jalr deasserted; alu_control selects SLL; wb_select selects the ALU result.
Forbidden: Do not inspect implementation internals.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.

## Publica — incremento 6

Behavior: A valid OP XOR selects the XOR ALU control while retaining the standard OP controls.
Coverage gap: RV32I register-register XOR decode has no public-port witness.
Prerequisites: The existing ADD and SUB cases witness the OP register-operand and writeback-control baseline.
New factor: OP funct3 selection of XOR.
Stimulus: A legal register-register XOR instruction with nonzero destination and source registers.
Support/witness path: 
Public observations: Check the complete public output tuple in port order: (1, 0, 0, 0, 0x5, 0, 0, 0, 0x0).
Forbidden: Do not inspect or require implementation internals.; Do not use an illegal or unsupported instruction encoding.; Do not claim coverage of other OP operations or instruction classes.

## Publica — incremento 6

Behavior: A legal OP SLL instruction selects alu_control=0010 and the standard OP control tuple.
Coverage gap: RV32I OP SLL function encoding
Prerequisites: The passing ADD case witnesses the OP class and its register-operand control tuple.; The passing SUB case witnesses OP function-field decoding.
New factor: SLL funct3 selects alu_control=0010.
Stimulus: A legal register-register SLL instruction with ordinary nonzero register indices.
Support/witness path: 
Public observations: {'reg_write': '1', 'mem_write': '0', 'alu_src_a_pc': '0', 'alu_src_b_imm': '0', 'alu_control': '0010', 'branch_enable': '0', 'jump': '0', 'jalr': '0', 'wb_select': '00'}
Forbidden: Do not inspect implementation internals.; Do not add unsupported or malformed instruction encodings.

## Publica — incremento 6

Behavior: AUIPC selects the PC as ALU operand A.
Coverage gap: AUIPC instruction-class control
Prerequisites: A passing LUI witness establishes immediate-operand selection for an upper-immediate instruction.; The public output alu_src_a_pc is available to observe the focal behavior.
New factor: PC selection as ALU operand A
Stimulus: A legal AUIPC instruction with a nonzero destination and representative upper immediate.
Support/witness path: 
Public observations: After the instruction input settles, alu_src_a_pc is asserted.
Forbidden: Do not inspect hierarchy or implementation internals.; Do not assert unrelated output behavior as newly covered.; Do not use instruction encodings that are illegal or unsupported by the assembler.

## Publica — incremento 6

Behavior: A valid register-register SLL selects the SLL ALU control while retaining the OP-class controls.
Coverage gap: RV32I OP SLL operation selection
Prerequisites: Valid OP-class controls are witnessed by ADD and SUB.
New factor: SLL operation selection
Stimulus: A legal register-register SLL instruction with a nonzero destination.
Support/witness path: None required.
Public observations: Check the complete public output tuple: reg_write asserted; mem_write, both jump controls, and branch_enable deasserted; both operand selectors choose registers; alu_control selects SLL; wb_select selects the ALU result.
Forbidden: Do not inspect internal signals.; Do not add unsupported or malformed instruction encodings.; Do not count the already witnessed OP-class controls as new coverage.

## Publica — incremento 6

Behavior: A valid register-register XOR selects alu_control=0x5 and the standard OP control tuple.
Coverage gap: RV32I OP XOR encoding: funct3=100 with funct7=0000000
Prerequisites: A valid OP instruction asserts reg_write and selects register operands, as witnessed by ADD.; A valid OP instruction can select a distinct ALU operation, as witnessed by SUB.
New factor: funct3=100 selects XOR
Stimulus: One legal RV32I register-register XOR instruction using ordinary nonzero destination and source registers.
Support/witness path: 
Public observations: {'ports': ['reg_write', 'mem_write', 'alu_src_a_pc', 'alu_src_b_imm', 'alu_control', 'branch_enable', 'jump', 'jalr', 'wb_select'], 'expected_tuple': '(1, 0, 0, 0, 0x5, 0, 0, 0, 0x0)'}
Forbidden: Do not require or inspect implementation internals.; Do not add another instruction or assert unrelated behaviors.

## Publica — incremento 6

Behavior: A valid SLL encoding selects the SLL ALU control while retaining the OP register-write and register-operand controls.
Coverage gap: RV32I OP SLL register-register encoding
Prerequisites: OP ADD decode has a passing public-port witness.; OP SUB decode has a passing public-port witness.
New factor: OP SLL function decode
Stimulus: A legal register-register SLL instruction using its valid base function encoding.
Support/witness path: None required.
Public observations: Check the complete output tuple: register write asserted; memory write, PC operand, branch, jump, and JALR inactive; immediate operand unselected; SLL selected by alu_control; ALU-result writeback selected.
Forbidden: Do not inspect implementation internals.; Do not use illegal, reserved, or malformed instruction encodings.; Do not add another ADD or SUB case with only different operand or register values.

## Publica — incremento 6

Behavior: For a valid register-register SLL instruction, decode the SLL ALU operation and retain the valid OP control tuple.
Coverage gap: Valid RV32I OP SLL operation selection.
Prerequisites: Valid OP decode is witnessed by ADD and SUB.; Register-writing OP controls are witnessed by ADD and SUB.
New factor: SLL operation selection.
Stimulus: Use a legal register-register SLL instruction with nonzero destination and source registers.
Support/witness path: None; the SLL selector is directly observable at the public alu_control port.
Public observations: Check the complete output tuple: reg_write asserted; mem_write, both PC/immediate source selects, branch_enable, jump, and jalr deasserted; alu_control selects SLL; wb_select selects the ALU result.
Forbidden: Do not inspect implementation internals.; Do not add a clock or reset stimulus.; Do not use an illegal or reserved instruction encoding.

## Publica — incremento 6

Behavior: For a valid register-register SLL instruction, assert the OP register-write and register-operand controls, with alu_control selecting SLL.
Coverage gap: Valid OP SLL encoding selects the SLL ALU control.
Prerequisites: A valid OP instruction is already witnessed by ADD and SUB.; The complete OP control tuple is already witnessed by ADD.
New factor: SLL operation selection
Stimulus: A valid register-register SLL instruction with otherwise ordinary OP fields.
Support/witness path: No support sequence is needed; use the direct instruction-to-controls witness. Existing ADD evidence establishes the OP-class controls.
Public observations: Check the complete public output tuple.; Confirm alu_control is the SLL selector and the other outputs match the valid OP class.
Forbidden: Do not inspect implementation internals.; Do not add another ADD or SUB case as a substitute for the SLL witness.; Do not use an illegal or reserved instruction encoding.

## Publica — incremento 6

Behavior: A valid register-register SLL instruction asserts register write, selects register operands, and selects SLL on alu_control.
Coverage gap: RV32I OP SLL function encoding selects the SLL ALU control
Prerequisites: The valid OP class and register-operand controls have passing public-port witnesses for ADD and SUB.
New factor: OP funct3 selects SLL
Stimulus: Use a legal RV32I register-register SLL instruction with a nonzero destination.
Support/witness path: None required; the existing ADD and SUB cases witness the OP-class controls.
Public observations: Check the complete output tuple: register write enabled, memory write disabled, both operand selectors low, alu_control selecting SLL, branch and jump controls inactive, and ALU writeback selected.
Forbidden: Do not inspect implementation internals.; Do not add an unsupported or malformed instruction encoding.; Do not claim additional OP operations or unsupported-encoding behavior as covered.

## Publica — incremento 6

Behavior: A valid OP-IMM XORI selects XOR on the ALU control while retaining the OP-IMM register-write and immediate-operand controls.
Coverage gap: OP-IMM XORI operation selection
Prerequisites: A passing ADDI witness establishes the OP-IMM class controls.; The ALU control is observable through the declared public port.
New factor: OP-IMM funct3 selects XOR
Stimulus: Use a legal XOR-immediate instruction with representative register operands and an immediate.
Support/witness path: None; observe the XORI controls directly through public ports. The existing ADDI case is prerequisite evidence, not a support stimulus.
Public observations: After the instruction settles, check the complete output tuple: register write asserted; memory write, PC operand selection, branch, jump, and JALR inactive; immediate operand selected; XOR ALU control selected; ALU-result writeback selected.
Forbidden: Do not inspect implementation internals.; Do not use illegal, reserved, or malformed instruction encodings.; Do not count the existing ADDI behavior as newly covered.

## Publica — incremento 6

Behavior: A valid register-register XOR selects ALU control 0x5 and otherwise has the OP control tuple.
Coverage gap: The valid RV32I OP XOR encoding has no public-port witness for its ALU selector.
Prerequisites: ADD witnesses the valid OP class and register-operand controls.; SUB witnesses selection of a distinct OP ALU operation.
New factor: OP XOR ALU selector
Stimulus: A legal register-register XOR instruction with a nonzero destination and source registers.
Support/witness path: None required; the instruction directly exposes the focal behavior through the declared outputs.
Public observations: {'reg_write': 1, 'mem_write': 0, 'alu_src_a_pc': 0, 'alu_src_b_imm': 0, 'alu_control': 5, 'branch_enable': 0, 'jump': 0, 'jalr': 0, 'wb_select': 0}
Forbidden: Do not require or inspect implementation internals.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.; Do not count ADD or SUB behavior as newly covered by this case.

## Publica — incremento 6

Behavior: A valid register-register SLL instruction asserts register write, selects register operands and ALU-result writeback, and selects alu_control 0x2; other class controls remain inactive.
Coverage gap: RV32I OP SLL encoding selects alu_control SLL
Prerequisites: A valid OP ADD has a public witness.; A valid OP SUB has a public witness.
New factor: OP SLL operation selection
Stimulus: A legal register-register SLL instruction with nonzero destination and representative source registers.
Support/witness path: None required.
Public observations: Check the complete output tuple against the valid OP controls.; Check alu_control is 0x2.
Forbidden: Do not inspect implementation internals.; Do not use illegal or unsupported instruction encodings.; Do not claim shift-result behavior; the decoder exposes only controls.

## Publica — incremento 6

Behavior: A valid register-register SLL instruction selects alu_control=0x2 and the valid OP control tuple.
Coverage gap: RV32I OP SLL function mapping
Prerequisites: A valid OP instruction produces register-write controls and selects register operands; witnessed by ADD.
New factor: SLL selects the SLL ALU control.
Stimulus: A legal register-register SLL instruction with ordinary nonzero destination and source registers.
Support/witness path: 
Public observations: reg_write=1; mem_write=0; alu_src_a_pc=0; alu_src_b_imm=0; alu_control=0x2; branch_enable=0; jump=0; jalr=0; wb_select=0x0
Forbidden: Do not require decoder internals.; Do not use an illegal or malformed instruction encoding.; Do not claim coverage of other OP operations or function restrictions.

## Publica — incremento 6

Behavior: A valid register-register XOR instruction selects the XOR operation.
Coverage gap: RV32I OP XOR ALU-control decoding
Prerequisites: A valid OP instruction’s register-operand control behavior is already witnessed by ADD and SUB cases.
New factor: OP funct3 decoding selects XOR.
Stimulus: A legal register-register XOR source instruction with a nonzero destination and two source registers.
Support/witness path: 
Public observations: After the instruction input settles, alu_control selects XOR.
Forbidden: Do not inspect implementation internals.; Do not add unsupported or malformed instruction encodings.

## Publica — incremento 7

Behavior: For a valid AUIPC instruction, alu_src_a_pc is asserted.
Coverage gap: AUIPC selects the PC as ALU operand A
Prerequisites: Existing ADDI evidence demonstrates immediate-operand selection; existing register-writing evidence demonstrates reg_write.
New factor: PC selection as ALU operand A
Stimulus: A legal AUIPC instruction with a nonzero destination and an immediate.
Support/witness path: None; the AUIPC instruction directly exposes the focal control through the public outputs.
Public observations: {'reg_write': 1, 'mem_write': 0, 'alu_src_a_pc': 1, 'alu_src_b_imm': 1, 'alu_control': '0000', 'branch_enable': 0, 'jump': 0, 'jalr': 0, 'wb_select': '00'}
Forbidden: Do not inspect decoder internals or require clock, reset, or memory ports.

## Publica — incremento 7

Behavior: A valid register-register AND instruction selects the AND ALU control.
Coverage gap: RV32I OP AND operation selection
Prerequisites: Valid OP controls are witnessed by ADD, SUB, and XOR cases.
New factor: AND ALU selection
Stimulus: Decode a legal register-register AND instruction accepted by assemble_rv32im.
Support/witness path: None; the focal behavior is directly observable on the alu_control output.
Public observations: alu_control selects AND.
Forbidden: Do not inspect implementation internals.; Do not assert unrelated outputs as additional coverage.; Do not use reserved, malformed, or illegal instruction encodings.

## Publica — incremento 8

Behavior: A valid register-register SLL instruction selects ALU control SLL.
Coverage gap: Valid RV32I OP SLL encoding and its ALU selector
Prerequisites: Valid OP decoding is witnessed by ADD, SUB, XOR, and AND cases.; The public ALU-control output is already checked for multiple OP operations.
New factor: SLL selects the SLL ALU operation.
Stimulus: A legal register-register SLL instruction using ordinary nonzero source and destination registers.
Support/witness path: 
Public observations: reg_write is asserted; mem_write, alu_src_a_pc, alu_src_b_imm, branch_enable, jump, and jalr are deasserted.; alu_control selects SLL.; wb_select selects the ALU result.
Forbidden: Do not require decoder internals.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.

## Publica — incremento 8

Behavior: A valid SLL instruction selects alu_control 0010 while retaining the OP register-write and register-operand controls.
Coverage gap: Valid register-register SLL decode: OP with funct3 001 and funct7 0000000 selects the SLL ALU operation.
Prerequisites: Passing public-port witnesses exist for OP ADD, SUB, XOR, and AND decoding.
New factor: SLL ALU-operation selection.
Stimulus: A legal register-register SLL instruction with ordinary nonzero source and destination registers.
Support/witness path: None; the SLL instruction directly provides the public witness.
Public observations: Check the complete output tuple: reg_write asserted; mem_write, alu_src_a_pc, alu_src_b_imm, branch_enable, jump, and jalr deasserted; alu_control selects SLL; wb_select selects the ALU result.
Forbidden: Do not inspect internals or use reserved, illegal, unallocated, or malformed instruction encodings.

## Publica — incremento 8

Behavior: A valid load asserts wb_select="01".
Coverage gap: Valid load instructions selecting the data-memory writeback source
Prerequisites: none
New factor: Load-class writeback selection
Stimulus: A legal word-load instruction with a nonzero destination and base register.
Support/witness path: None; the selected writeback source is directly observable.
Public observations: wb_select="01"
Forbidden: Do not inspect implementation internals.; Do not require an actual memory read or register-file effect.

## Publica — incremento 8

Behavior: A valid OR instruction selects ALU control 1000 and otherwise has the valid OP control tuple.
Coverage gap: Valid register-register OR (OP with funct3=110 and funct7=0000000) ALU-control selection.
Prerequisites: Valid OP decoding is witnessed by ADD, SUB, XOR, and AND cases.; The public alu_control output is already checked.
New factor: OR operation selection
Stimulus: A legal register-register OR instruction with a nonzero destination.
Support/witness path: None; the focal behavior is directly observable from the instruction input and decoder outputs.
Public observations: {'ports': ['reg_write', 'mem_write', 'alu_src_a_pc', 'alu_src_b_imm', 'alu_control', 'branch_enable', 'jump', 'jalr', 'wb_select'], 'expected_tuple': [1, 0, 0, 0, 8, 0, 0, 0, 0]}
Forbidden: Do not inspect or require implementation internals.; Do not add clock or reset stimulus.; Do not use unsupported or malformed instruction encodings.; Do not claim coverage of other missing ALU operations or instruction classes.

## Publica — incremento 8

Behavior: A valid SLTI instruction selects alu_control for signed comparison.
Coverage gap: OP-IMM SLTI selects the signed SLT ALU operation
Prerequisites: The passing ADDI witness establishes the OP-IMM class and immediate-operand selection.
New factor: SLTI selects the signed-comparison ALU operation.
Stimulus: A legal SLTI instruction with an ordinary nonzero destination and register source.
Support/witness path: No support sequence is needed; the focal behavior is directly observable.
Public observations: Check alu_control is 0x3.
Forbidden: Do not inspect implementation internals.; Do not assert unrelated outputs as evidence for this focal behavior.

## Publica — incremento 8

Behavior: A valid load selects the data-memory result for writeback.
Coverage gap: Valid load instructions select data-memory writeback with wb_select="01".
Prerequisites: none
New factor: Load writeback selection
Stimulus: A legal word-load instruction with a nonzero destination register.
Support/witness path: None; the load instruction directly witnesses the behavior.
Public observations: wb_select is "01".
Forbidden: Do not require internal signals or hierarchy access.; Do not add clock or reset stimulus.; Do not assert unrelated output behaviors as newly covered.; Do not use illegal or malformed instruction encodings.

## Publica — incremento 8

Behavior: A valid load asserts register write, selects the immediate as ALU operand B, uses ADD, and selects data-memory writeback.
Coverage gap: Valid load-class selection of data-memory writeback (`wb_select="01"`) has no public-port witness.
Prerequisites: None; the decoder is combinational and the behavior is directly observable from the instruction and output ports.
New factor: Data-memory writeback selection for a valid load.
Stimulus: A valid word load with a nonzero destination register.
Support/witness path: None; the load itself is the public witness.
Public observations: Check the complete output tuple: reg_write=1, mem_write=0, alu_src_a_pc=0, alu_src_b_imm=1, alu_control=0x0, branch_enable=0, jump=0, jalr=0, and wb_select=0x1.
Forbidden: Do not inspect implementation internals or infer load behavior from an unrelated instruction class.

## Publica — incremento 8

Behavior: A valid SLT OP instruction selects signed-less-than on the ALU while retaining the valid OP control tuple.
Coverage gap: RV32I OP signed-less-than (SLT) function encoding and its ALU selector
Prerequisites: A valid OP class has passing witnesses through ADD, SUB, XOR, and AND.; No support sequence is needed.
New factor: SLT selects the signed-less-than ALU operation.
Stimulus: A legal register-register signed-less-than instruction.
Support/witness path: None.
Public observations: Check the complete output tuple: reg_write asserted; mem_write, alu_src_a_pc, alu_src_b_imm, branch_enable, jump, and jalr deasserted; alu_control selects SLT; wb_select selects the ALU result.
Forbidden: Do not inspect implementation internals.; Do not assert an ALU comparison result; the decoder exposes controls only.; Do not treat this case as evidence for other OP operations or unsupported encodings.

## Publica — incremento 8

Behavior: A legal store asserts mem_write and selects the immediate as ALU operand B, without asserting register write or other side-effect controls.
Coverage gap: Valid store instruction controls
Prerequisites: None; the decoder is combinational and the case can use a legal store instruction directly.
New factor: Valid store classification
Stimulus: A canonical legal SW instruction using nonzero source registers.
Support/witness path: None; use the store instruction directly.
Public observations: Check the complete output tuple: reg_write inactive, mem_write active, alu_src_a_pc inactive, alu_src_b_imm active, ADD selected, branch_enable/jump/jalr inactive, and ALU-result writeback selected.
Forbidden: Do not inspect internals or add clock/reset stimulus. Do not use illegal or reserved encodings, or claim load, branch, jump, or unsupported-encoding coverage from this case.

## Publica — incremento 8

Behavior: A valid register-register OR instruction selects the OR operation.
Coverage gap: Valid RV32I OP OR encoding and its OR ALU selector
Prerequisites: The suite already witnesses valid OP register-register decoding and distinct ADD, SUB, XOR, and AND selectors.
New factor: OR operation selection
Stimulus: A legal register-register OR instruction using nonzero register indices.
Support/witness path: 
Public observations: Check the complete public control tuple: register write enabled; memory write, PC operand selection, immediate operand selection, branch, jump, and JALR inactive; OR selected by alu_control; ALU-result writeback selected.
Forbidden: Do not inspect implementation internals or introduce unrelated instruction classes or edge cases.

## Publica — incremento 8

Behavior: A valid register-register OR instruction asserts register write, selects register operands, keeps memory, branch, and jump controls inactive, selects ALU writeback, and selects the OR ALU operation.
Coverage gap: The valid OP OR encoding has no public-port witness selecting the OR ALU operation.
Prerequisites: Passing witnesses establish valid OP controls through ADD, SUB, XOR, and AND instructions.
New factor: OR ALU operation selection
Stimulus: Use a legal register-register OR instruction with nonzero register fields.
Support/witness path: None; the focal behavior is directly observable from the instruction and decoder outputs.
Public observations: Check the complete output tuple: reg_write is asserted; mem_write, alu_src_a_pc, alu_src_b_imm, branch_enable, jump, and jalr are inactive; wb_select selects ALU writeback; alu_control selects OR.
Forbidden: Do not inspect internals or add unsupported or malformed instruction encodings.

## Publica — incremento 8

Behavior: A valid register-register SLL instruction selects SLL on alu_control.
Coverage gap: RV32I OP SLL encoding and its ALU selector
Prerequisites: Valid OP decoding is witnessed by the ADD, SUB, XOR, and AND cases.
New factor: SLL selects the SLL ALU operation.
Stimulus: A legal register-register SLL instruction with a nonzero destination.
Support/witness path: None required.
Public observations: Check the complete output tuple: register write enabled; memory write, PC operand selection, immediate operand selection, branch, jump, and JALR inactive; alu_control selects SLL; writeback selects the ALU result.
Forbidden: Do not inspect implementation internals.; Do not add a clock or reset stimulus.; Do not count the already witnessed general OP decoding as new coverage.

## Publica — incremento 8

Behavior: A valid load sets wb_select to the data-memory result selector.
Coverage gap: Valid load instruction class selects data-memory writeback.
Prerequisites: None. Existing ADDI evidence covers immediate-operand selection, and existing register-writing cases cover reg_write.
New factor: Load-class writeback selection.
Stimulus: A legal word load with a nonzero destination and base register.
Support/witness path: No support sequence is required; observe the load’s outputs directly through the declared ports.
Public observations: Check the complete output tuple: reg_write asserted; mem_write, alu_src_a_pc, branch_enable, jump, and jalr deasserted; alu_src_b_imm asserted; alu_control selects ADD; wb_select selects data-memory read.
Forbidden: Do not inspect internals or introduce a clock or reset. Do not count the already-witnessed immediate-source or register-write behavior as new coverage.

## Publica — incremento 8

Behavior: An RV32M OP encoding is recognized as a valid register-writing OP instruction with the specified default ALU control.
Coverage gap: RV32M OP encodings are not yet witnessed: no legal instruction with funct7=0000001 has been checked.
Prerequisites: Existing ADD and SUB witnesses establish valid OP decoding and public OP control outputs.
New factor: RV32M funct7 recognition
Stimulus: A legal RV32IM MUL instruction using nonzero destination and source registers.
Support/witness path: None; the focal instruction directly exercises RV32M recognition.
Public observations: Check the complete declared output tuple: register write enabled; memory write, branch, jump, and JALR inactive; register operands selected; ALU control at its RV32M default; and ALU-result writeback selected.
Forbidden: Do not inspect hierarchy or require internals; do not infer arithmetic results from this decoder; do not use illegal encodings or enumerate all RV32M funct3 values.

## Publica — incremento 9

Behavior: A valid OP OR instruction selects OR on the ALU and asserts the valid OP control tuple.
Coverage gap: RV32I OP OR function encoding
Prerequisites: none
New factor: OR ALU selection
Stimulus: Use a legal register-register OR instruction with nonzero destination and source registers.
Support/witness path: None required.
Public observations: After the instruction settles, check alu_control selects OR and verify the complete public output tuple for a valid OP instruction.
Forbidden: Do not inspect internals or use an unsupported instruction encoding.

## Publica — incremento 9

Behavior: A valid register-register SLT instruction selects the signed-less-than ALU operation.
Coverage gap: RV32I OP signed-less-than (SLT) function mapping
Prerequisites: The OP register-register class and its baseline controls are already witnessed by the passing ADD and SUB cases.
New factor: SLT selects the signed-less-than ALU control.
Stimulus: A legal RV32I register-register signed-less-than instruction using distinct nonzero source and destination registers.
Support/witness path: None required.
Public observations: Check that alu_control selects signed less-than.
Forbidden: Do not use internal signals, invalid encodings, or add unrelated assertions about other instruction classes.

## Publica — incremento 9

Behavior: Unsupported opcode selects the defined default controls.
Coverage gap: A legal FENCE instruction, whose opcode is unsupported by this decoder, produces the complete no-side-effect default output tuple.
Prerequisites: None; this is directly observable from a single instruction on the public interface.
New factor: Unsupported-opcode default controls.
Stimulus: A legal FENCE instruction accepted by assemble_rv32im.
Support/witness path: None; the instruction itself is the focal stimulus.
Public observations: After the instruction settles, check every declared output: all control outputs, alu_control, and wb_select are zero.
Forbidden: Do not use an illegal, reserved, unallocated, or malformed encoding; do not inspect internal signals.

