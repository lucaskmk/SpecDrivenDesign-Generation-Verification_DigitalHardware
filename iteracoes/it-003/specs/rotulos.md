# Rótulos de rastreabilidade

Catálogo fixo de pontos de checagem derivado das specs. Só vai para a IA com
`rvgen gerar --rotulos`. A IA **não inventa** rótulos: o contrato de cada
bloco lista, na seção `## Labels`, os `CK-*` deste arquivo pelos quais o
bloco responde, e cada teste cocotb cita, num comentário `# CK: ...`, os
rótulos que verifica. Um verificador sem IA (`rvgen/rotulos.py`) recusa
rótulo que não está aqui e mede quais rótulos ficaram sem teste.

Hierarquia: `FG-*` (grupo funcional) → `FC-*` (função) → `CK-*` (ponto de
checagem). Grupos marcados `[RV32M]` só valem quando o `cpu.md` declara
RV32IM. Entre parênteses, a spec de onde o ponto saiu.

## FG-RV32I-ALU — aritmética e lógica inteira

### FC-ADD — soma (`add`, `addi`)
- CK-ADD-BASICO: soma de dois operandos (riscv-rv32i.md)
- CK-ADD-WRAP: resultado reduzido a 32 bits, sem exceção de overflow (riscv-rv32i.md)
- CK-ADDI-IMM-NEG: imediato de 12 bits estendido com sinal (riscv-rv32i.md)

### FC-SUB — subtração (`sub`)
- CK-SUB-BASICO: diferença rs1 − rs2 (riscv-rv32i.md)
- CK-SUB-WRAP: resultado reduzido a 32 bits (riscv-rv32i.md)

### FC-LOGICA — `and`, `or`, `xor` e versões com imediato
- CK-AND: E bit a bit (riscv-rv32i.md)
- CK-OR: OU bit a bit (riscv-rv32i.md)
- CK-XOR: OU exclusivo bit a bit (riscv-rv32i.md)

### FC-SHIFT — deslocamentos
- CK-SLL: deslocamento lógico à esquerda (riscv-rv32i.md)
- CK-SRL: deslocamento lógico à direita, entra zero (riscv-rv32i.md)
- CK-SRA-SINAL: deslocamento aritmético à direita, replica o bit de sinal (riscv-rv32i.md)
- CK-SHAMT-5BITS: só os 5 bits baixos de rs2/shamt contam (riscv-rv32i.md)

### FC-COMPARA — `slt`, `sltu` e versões com imediato
- CK-SLT-SINAL: comparação com sinal devolve 1 ou 0 (riscv-rv32i.md)
- CK-SLTU-SEMSINAL: comparação sem sinal devolve 1 ou 0 (riscv-rv32i.md)

### FC-UPPER — `lui`, `auipc`
- CK-LUI: imediato nos 20 bits altos, 12 baixos zerados (riscv-rv32i.md)
- CK-AUIPC: PC da instrução mais o imediato alto (riscv-rv32i.md)

## FG-RV32I-MEM — acesso à memória

### FC-LOAD — leituras
- CK-LW: palavra de 32 bits (riscv-rv32i.md)
- CK-LH-SINAL: meia palavra estendida com sinal (riscv-rv32i.md, cpu.md)
- CK-LHU-ZERO: meia palavra estendida com zero (riscv-rv32i.md, cpu.md)
- CK-LB-SINAL: byte estendido com sinal (riscv-rv32i.md, cpu.md)
- CK-LBU-ZERO: byte estendido com zero (riscv-rv32i.md, cpu.md)
- CK-LOAD-ENDERECO: endereço = rs1 + imediato com sinal (riscv-rv32i.md)

### FC-STORE — escritas
- CK-SW: grava a palavra inteira (riscv-rv32i.md, cpu.md)
- CK-SH: grava só a meia palavra endereçada (riscv-rv32i.md, cpu.md)
- CK-SB: grava só o byte endereçado (riscv-rv32i.md, cpu.md)

## FG-RV32I-CTRL — fluxo de controle

### FC-BRANCH — desvios condicionais
- CK-BEQ-BNE: igualdade e diferença (riscv-rv32i.md)
- CK-BLT-BGE-SINAL: comparação com sinal (riscv-rv32i.md)
- CK-BLTU-BGEU-SEMSINAL: comparação sem sinal (riscv-rv32i.md)
- CK-BRANCH-NAO-TOMADO: condição falsa segue para PC + 4 (riscv-rv32i.md)
- CK-BRANCH-ALVO: alvo = PC da instrução + imediato B com sinal (riscv-rv32i.md)

### FC-JUMP — saltos
- CK-JAL-LINK: `jal` grava PC + 4 em rd e salta para PC + imediato J (riscv-rv32i.md)
- CK-JALR-LSB-ZERO: `jalr` salta para (rs1 + imediato) com o bit 0 zerado (riscv-rv32i.md)

## FG-RV32I-ESTADO — registradores e PC

### FC-REG — banco de registradores
- CK-X0-ZERO: `x0` sempre lê zero e escrita nele é ignorada (riscv-rv32i.md)
- CK-REG-ESCRITA-LEITURA: valor escrito em rd é lido depois em rs1/rs2 (riscv-rv32i.md)

### FC-PC — contador de programa
- CK-RESET-PC: depois do reset o PC é 0x00000000 (cpu.md)
- CK-PC-MAIS-4: instrução que não desvia avança o PC em 4 (riscv-rv32i.md)

## FG-RV32M — multiplicação e divisão [RV32M]

### FC-MUL — `mul`
- CK-MUL-BAIXO: 32 bits baixos do produto (riscv-rv32m.md)

### FC-MULH — `mulh`, `mulhsu`, `mulhu`
- CK-MULH-SINAL: 32 bits altos com os dois operandos com sinal (riscv-rv32m.md)
- CK-MULHSU-MISTO: rs1 com sinal, rs2 sem sinal (riscv-rv32m.md)
- CK-MULHU-SEMSINAL: 32 bits altos com os dois sem sinal (riscv-rv32m.md)

### FC-DIV — `div`
- CK-DIV-TRUNCA: quociente com sinal truncado para zero (riscv-rv32m.md)
- CK-DIV-ZERO: divisor zero (riscv-rv32m.md)
- CK-DIV-OVERFLOW: dividendo −2^31 e divisor −1 (riscv-rv32m.md)

### FC-DIVU — `divu`
- CK-DIVU-BASICO: quociente sem sinal (riscv-rv32m.md)
- CK-DIVU-ZERO: divisor zero (riscv-rv32m.md)

### FC-REM — `rem`
- CK-REM-SINAL-DIVIDENDO: resto com o sinal do dividendo (riscv-rv32m.md)
- CK-REM-ZERO: divisor zero (riscv-rv32m.md)
- CK-REM-OVERFLOW: dividendo −2^31 e divisor −1 (riscv-rv32m.md)

### FC-REMU — `remu`
- CK-REMU-BASICO: resto sem sinal (riscv-rv32m.md)
- CK-REMU-ZERO: divisor zero (riscv-rv32m.md)
