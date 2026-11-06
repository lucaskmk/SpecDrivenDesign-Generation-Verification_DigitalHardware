## Publica — incremento 1

Behavior: A legal RV32M instruction produces valid = 1.
Coverage gap: Positive recognition of a legal RV32M instruction is not directly observed: the passing suite does not check valid.
Prerequisites: None; the inputs and combinational outputs are public.
New factor: Positive RV32M instruction recognition.
Stimulus: Present a legal RV32IM MUL instruction with the required RV32M opcode and function code.
Support/witness path: None; recognition is directly observable through valid.
Public observations: Check that valid is 1.
Forbidden: Do not inspect internals, use malformed or reserved encodings, or count arithmetic results as additional coverage in this case.

## Publica — incremento 2

Behavior: A legal MUL instruction returns the low 32 bits of the operand product.
Coverage gap: MUL low-32-bit product result
Prerequisites: Legal MUL recognition has a public-port witness.
New factor: MUL product result
Stimulus: Use a legal MUL source with operands chosen so the low product is nonzero and differs from either operand.
Support/witness path: No support sequence is needed.
Public observations: valid is asserted.; result equals the low 32 bits of the operand product.
Forbidden: Do not inspect implementation internals.; Do not use an illegal or malformed instruction encoding.

## Publica — incremento 3

Behavior: Signed DIV produces the ordinary quotient for a nonzero divisor.
Coverage gap: Nonzero-divisor DIV quotient behavior
Prerequisites: The suite witnesses M-instruction recognition with a legal MUL.; The suite witnesses the DIV zero-divisor result.
New factor: Nonzero-divisor DIV quotient
Stimulus: A legal DIV instruction with positive operands and a nonzero divisor that does not divide the dividend evenly.
Support/witness path: 
Public observations: valid is asserted.; result equals the signed quotient rounded toward zero.
Forbidden: Do not require internal signals or hierarchy access.; Do not use an illegal, reserved, or malformed instruction encoding.; Do not claim signed truncation for negative operands, other operation selectors, or additional division edge cases as newly covered.

## Publica — incremento 4

Behavior: MUL returns only bits 31:0 of the full product.
Coverage gap: MUL low-32-bit truncation when the full product has nonzero upper bits
Prerequisites: A legal MUL instruction is recognized: witnessed by lote-001-caso-01.py.; A nominal MUL result is correct: witnessed by lote-002-caso-01.py.
New factor: Product truncation
Stimulus: Use a legal MUL source accepted by assemble_rv32im, with operands whose full product has nonzero upper bits and a nonzero low 32-bit result.
Support/witness path: None required; the existing MUL recognition witness supplies the prerequisite.
Public observations: valid is 1.; result equals the low 32 bits of the full product.
Forbidden: Do not require internal signals or hierarchy.; Do not use reserved, illegal, unallocated, or malformed instruction encodings.; Do not add unrelated operation selectors or edge cases.

