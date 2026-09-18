#!/usr/bin/env python3
"""RV32IM instruction encoder/decoder used as an independent oracle.

# REQ: FR-03, FR-04, FR-14 (design) / pipeline:FR-25

Two jobs:
  * `encode(...)` builds instruction words for the block-level tests of the
    control unit -- so the decoder under test is checked against words this
    module produced from the RISC-V format tables, not from the DUT.
  * `decode(word)` maps a retired instruction word back to a mnemonic, which
    is how phase 4b measures coverage *dynamically* (pipeline:FR-25): the
    mnemonic comes from what the CPU actually retired on `dbg_instr`, never
    from the assembly source, which would pass even for dead code.

Only the 45 instructions declared in specs/spec.json are recognised.
Anything else decodes as None, which is what makes an unexpected retirement
visible as a spec gap (pipeline:FR-27) instead of being silently absorbed.
"""
from __future__ import annotations

MASK32 = 0xFFFFFFFF

OPC_LUI = 0b0110111
OPC_AUIPC = 0b0010111
OPC_JAL = 0b1101111
OPC_JALR = 0b1100111
OPC_BRANCH = 0b1100011
OPC_LOAD = 0b0000011
OPC_STORE = 0b0100011
OPC_OP_IMM = 0b0010011
OPC_OP = 0b0110011

# mnemonic -> (opcode, funct3, funct7)  (None = field not used / don't care)
R_TYPE = {
    "add":  (OPC_OP, 0b000, 0b0000000),
    "sub":  (OPC_OP, 0b000, 0b0100000),
    "sll":  (OPC_OP, 0b001, 0b0000000),
    "slt":  (OPC_OP, 0b010, 0b0000000),
    "sltu": (OPC_OP, 0b011, 0b0000000),
    "xor":  (OPC_OP, 0b100, 0b0000000),
    "srl":  (OPC_OP, 0b101, 0b0000000),
    "sra":  (OPC_OP, 0b101, 0b0100000),
    "or":   (OPC_OP, 0b110, 0b0000000),
    "and":  (OPC_OP, 0b111, 0b0000000),
    # M extension
    "mul":    (OPC_OP, 0b000, 0b0000001),
    "mulh":   (OPC_OP, 0b001, 0b0000001),
    "mulhsu": (OPC_OP, 0b010, 0b0000001),
    "mulhu":  (OPC_OP, 0b011, 0b0000001),
    "div":    (OPC_OP, 0b100, 0b0000001),
    "divu":   (OPC_OP, 0b101, 0b0000001),
    "rem":    (OPC_OP, 0b110, 0b0000001),
    "remu":   (OPC_OP, 0b111, 0b0000001),
}

I_TYPE = {
    "addi":  (OPC_OP_IMM, 0b000),
    "slti":  (OPC_OP_IMM, 0b010),
    "sltiu": (OPC_OP_IMM, 0b011),
    "xori":  (OPC_OP_IMM, 0b100),
    "ori":   (OPC_OP_IMM, 0b110),
    "andi":  (OPC_OP_IMM, 0b111),
    "lb":    (OPC_LOAD, 0b000),
    "lh":    (OPC_LOAD, 0b001),
    "lw":    (OPC_LOAD, 0b010),
    "lbu":   (OPC_LOAD, 0b100),
    "lhu":   (OPC_LOAD, 0b101),
    "jalr":  (OPC_JALR, 0b000),
}

SHIFT_IMM = {
    "slli": (0b001, 0b0000000),
    "srli": (0b101, 0b0000000),
    "srai": (0b101, 0b0100000),
}

S_TYPE = {"sb": 0b000, "sh": 0b001, "sw": 0b010}

B_TYPE = {"beq": 0b000, "bne": 0b001, "blt": 0b100,
          "bge": 0b101, "bltu": 0b110, "bgeu": 0b111}

U_TYPE = {"lui": OPC_LUI, "auipc": OPC_AUIPC}

ALL_MNEMONICS = (
    set(R_TYPE) | set(I_TYPE) | set(SHIFT_IMM) | set(S_TYPE)
    | set(B_TYPE) | set(U_TYPE) | {"jal"}
)


def _bits(word: int, high: int, low: int) -> int:
    return (word >> low) & ((1 << (high - low + 1)) - 1)


# ---------------------------------------------------------------------------
# Encoding
# ---------------------------------------------------------------------------
def encode(mnemonic: str, rd: int = 0, rs1: int = 0, rs2: int = 0,
           imm: int = 0) -> int:
    """Build the 32-bit word of one instruction."""
    if mnemonic in R_TYPE:
        opcode, funct3, funct7 = R_TYPE[mnemonic]
        return ((funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12)
                | (rd << 7) | opcode) & MASK32
    if mnemonic in SHIFT_IMM:
        funct3, funct7 = SHIFT_IMM[mnemonic]
        return ((funct7 << 25) | ((imm & 0x1F) << 20) | (rs1 << 15)
                | (funct3 << 12) | (rd << 7) | OPC_OP_IMM) & MASK32
    if mnemonic in I_TYPE:
        opcode, funct3 = I_TYPE[mnemonic]
        return (((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12)
                | (rd << 7) | opcode) & MASK32
    if mnemonic in S_TYPE:
        funct3 = S_TYPE[mnemonic]
        imm &= 0xFFF
        return ((_bits(imm, 11, 5) << 25) | (rs2 << 20) | (rs1 << 15)
                | (funct3 << 12) | (_bits(imm, 4, 0) << 7) | OPC_STORE) & MASK32
    if mnemonic in B_TYPE:
        funct3 = B_TYPE[mnemonic]
        imm &= 0x1FFF
        return ((_bits(imm, 12, 12) << 31) | (_bits(imm, 10, 5) << 25)
                | (rs2 << 20) | (rs1 << 15) | (funct3 << 12)
                | (_bits(imm, 4, 1) << 8) | (_bits(imm, 11, 11) << 7)
                | OPC_BRANCH) & MASK32
    if mnemonic in U_TYPE:
        opcode = U_TYPE[mnemonic]
        return (((imm >> 12) & 0xFFFFF) << 12 | (rd << 7) | opcode) & MASK32
    if mnemonic == "jal":
        imm &= 0x1FFFFF
        return ((_bits(imm, 20, 20) << 31) | (_bits(imm, 10, 1) << 21)
                | (_bits(imm, 11, 11) << 20) | (_bits(imm, 19, 12) << 12)
                | (rd << 7) | OPC_JAL) & MASK32
    raise ValueError(f"cannot encode {mnemonic!r}")


# ---------------------------------------------------------------------------
# Decoding (dynamic coverage oracle)
# ---------------------------------------------------------------------------
def decode(word: int) -> str | None:
    """Map an instruction word to one of the 45 declared mnemonics.

    Returns None for anything not declared in spec.json (FR-14), including
    fence/ecall/ebreak/CSR and reserved funct3/funct7 encodings.
    """
    word &= MASK32
    opcode = _bits(word, 6, 0)
    funct3 = _bits(word, 14, 12)
    funct7 = _bits(word, 31, 25)

    if opcode == OPC_LUI:
        return "lui"
    if opcode == OPC_AUIPC:
        return "auipc"
    if opcode == OPC_JAL:
        return "jal"
    if opcode == OPC_JALR:
        return "jalr" if funct3 == 0 else None
    if opcode == OPC_BRANCH:
        for name, f3 in B_TYPE.items():
            if f3 == funct3:
                return name
        return None
    if opcode == OPC_LOAD:
        for name, (opc, f3) in I_TYPE.items():
            if opc == OPC_LOAD and f3 == funct3:
                return name
        return None
    if opcode == OPC_STORE:
        for name, f3 in S_TYPE.items():
            if f3 == funct3:
                return name
        return None
    if opcode == OPC_OP_IMM:
        if funct3 in (0b001, 0b101):
            for name, (f3, f7) in SHIFT_IMM.items():
                if f3 == funct3 and f7 == funct7:
                    return name
            return None
        for name, (opc, f3) in I_TYPE.items():
            if opc == OPC_OP_IMM and f3 == funct3:
                return name
        return None
    if opcode == OPC_OP:
        for name, (opc, f3, f7) in R_TYPE.items():
            if f3 == funct3 and f7 == funct7:
                return name
        return None
    return None
