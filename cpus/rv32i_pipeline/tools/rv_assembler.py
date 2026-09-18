#!/usr/bin/env python3
"""Montador RV32I / RV32IM determinístico.

REQ: FR-RV-19 (programas .asm), FR-RV-20 (alternativa registrada à ausência
de compilador RISC-V), FR-RV-03 (ISA estritamente RISC-V).

Contexto: não existe compilador RISC-V neste ambiente (ver
`specs/decisions.md`, ADR-004). Este montador é a alternativa adotada, e é
código do projeto — portanto entra na cadeia de rastreabilidade e é validado
por pytest contra os encodings da especificação RISC-V não privilegiada
ANTES de ser usado para gerar imagens de teste da CPU.

Escopo deliberado: apenas RV32I base e a extensão M. Nenhuma instrução fora
do RISC-V é aceita (FR-RV-03). `FENCE`, `ECALL` e `EBREAK` são reconhecidas
mas rejeitadas por padrão, porque a CPU alvo não as implementa (ver ADR-000).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

WORD_BYTES = 4
XLEN = 32


class AssemblyError(Exception):
    """Erro de montagem com localização no arquivo fonte."""

    def __init__(self, message: str, line_no: int | None = None, text: str | None = None):
        self.line_no = line_no
        self.text = text
        if line_no is not None:
            message = f"linha {line_no}: {message}"
            if text:
                message += f"\n    {text.strip()}"
        super().__init__(message)


# --------------------------------------------------------------------------
# Registradores: x0..x31 e nomes ABI
# --------------------------------------------------------------------------

_ABI_NAMES = {
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7,
    "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14, "a5": 15, "a6": 16, "a7": 17,
    "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22, "s7": 23,
    "s8": 24, "s9": 25, "s10": 26, "s11": 27,
    "t3": 28, "t4": 29, "t5": 30, "t6": 31,
}


def parse_register(token: str) -> int:
    """Traduz `x5`, `t0`, `sp` etc. para o índice 0..31."""
    t = token.strip().lower()
    if t in _ABI_NAMES:
        return _ABI_NAMES[t]
    m = re.fullmatch(r"x(\d+)", t)
    if m:
        idx = int(m.group(1))
        if 0 <= idx <= 31:
            return idx
        raise AssemblyError(f"registrador fora da faixa x0..x31: {token!r}")
    raise AssemblyError(f"registrador inválido: {token!r}")


# --------------------------------------------------------------------------
# Tabelas de instruções (encodings da spec RISC-V não privilegiada)
# --------------------------------------------------------------------------

OPCODE_LUI = 0b0110111
OPCODE_AUIPC = 0b0010111
OPCODE_JAL = 0b1101111
OPCODE_JALR = 0b1100111
OPCODE_BRANCH = 0b1100011
OPCODE_LOAD = 0b0000011
OPCODE_STORE = 0b0100011
OPCODE_OP_IMM = 0b0010011
OPCODE_OP = 0b0110011

FUNCT7_M = 0b0000001

# mnemônico -> (funct3, funct7)
R_TYPE = {
    "add": (0b000, 0b0000000), "sub": (0b000, 0b0100000),
    "sll": (0b001, 0b0000000), "slt": (0b010, 0b0000000),
    "sltu": (0b011, 0b0000000), "xor": (0b100, 0b0000000),
    "srl": (0b101, 0b0000000), "sra": (0b101, 0b0100000),
    "or": (0b110, 0b0000000), "and": (0b111, 0b0000000),
}

# extensão M — todas com funct7 = 0000001 (FR-RV-13)
M_TYPE = {
    "mul": 0b000, "mulh": 0b001, "mulhsu": 0b010, "mulhu": 0b011,
    "div": 0b100, "divu": 0b101, "rem": 0b110, "remu": 0b111,
}

I_TYPE_ARITH = {
    "addi": 0b000, "slti": 0b010, "sltiu": 0b011,
    "xori": 0b100, "ori": 0b110, "andi": 0b111,
}

# shifts imediatos: (funct3, funct7)
I_TYPE_SHIFT = {
    "slli": (0b001, 0b0000000),
    "srli": (0b101, 0b0000000),
    "srai": (0b101, 0b0100000),
}

LOADS = {"lb": 0b000, "lh": 0b001, "lw": 0b010, "lbu": 0b100, "lhu": 0b101}
STORES = {"sb": 0b000, "sh": 0b001, "sw": 0b010}
BRANCHES = {
    "beq": 0b000, "bne": 0b001, "blt": 0b100,
    "bge": 0b101, "bltu": 0b110, "bgeu": 0b111,
}

# não implementadas pela CPU alvo (ADR-000)
UNSUPPORTED_BY_CPU = {"fence", "fence.i", "ecall", "ebreak"}


# --------------------------------------------------------------------------
# Helpers de bits
# --------------------------------------------------------------------------

def _check_signed(value: int, bits: int, what: str) -> int:
    lo, hi = -(1 << (bits - 1)), (1 << (bits - 1)) - 1
    if not lo <= value <= hi:
        raise AssemblyError(
            f"{what} fora da faixa de {bits} bits com sinal "
            f"({value} não está em [{lo}, {hi}])"
        )
    return value & ((1 << bits) - 1)


def _check_unsigned(value: int, bits: int, what: str) -> int:
    if not 0 <= value < (1 << bits):
        raise AssemblyError(
            f"{what} fora da faixa de {bits} bits sem sinal "
            f"({value} não está em [0, {(1 << bits) - 1}])"
        )
    return value


def enc_r(funct7: int, rs2: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    return ((funct7 & 0x7F) << 25 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15
            | (funct3 & 0x7) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F))


def enc_i(imm: int, rs1: int, funct3: int, rd: int, opcode: int) -> int:
    return ((imm & 0xFFF) << 20 | (rs1 & 0x1F) << 15 | (funct3 & 0x7) << 12
            | (rd & 0x1F) << 7 | (opcode & 0x7F))


def enc_s(imm: int, rs2: int, rs1: int, funct3: int, opcode: int) -> int:
    imm &= 0xFFF
    return (((imm >> 5) & 0x7F) << 25 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15
            | (funct3 & 0x7) << 12 | (imm & 0x1F) << 7 | (opcode & 0x7F))


def enc_b(imm: int, rs2: int, rs1: int, funct3: int, opcode: int) -> int:
    """imm é o deslocamento em bytes, múltiplo de 2, 13 bits com sinal."""
    imm &= 0x1FFF
    bit12 = (imm >> 12) & 0x1
    bits10_5 = (imm >> 5) & 0x3F
    bits4_1 = (imm >> 1) & 0xF
    bit11 = (imm >> 11) & 0x1
    return (bit12 << 31 | bits10_5 << 25 | (rs2 & 0x1F) << 20 | (rs1 & 0x1F) << 15
            | (funct3 & 0x7) << 12 | bits4_1 << 8 | bit11 << 7 | (opcode & 0x7F))


def enc_u(imm20: int, rd: int, opcode: int) -> int:
    return ((imm20 & 0xFFFFF) << 12 | (rd & 0x1F) << 7 | (opcode & 0x7F))


def enc_j(imm: int, rd: int, opcode: int) -> int:
    """imm é o deslocamento em bytes, múltiplo de 2, 21 bits com sinal."""
    imm &= 0x1FFFFF
    bit20 = (imm >> 20) & 0x1
    bits10_1 = (imm >> 1) & 0x3FF
    bit11 = (imm >> 11) & 0x1
    bits19_12 = (imm >> 12) & 0xFF
    return ((bit20 << 31) | (bits10_1 << 21) | (bit11 << 20) | (bits19_12 << 12)
            | ((rd & 0x1F) << 7) | (opcode & 0x7F))


# --------------------------------------------------------------------------
# Parsing de linha
# --------------------------------------------------------------------------

@dataclass
class SourceLine:
    line_no: int
    raw: str
    labels: list[str] = field(default_factory=list)
    mnemonic: str | None = None
    operands: list[str] = field(default_factory=list)
    address: int = 0
    size: int = 0


_COMMENT_RE = re.compile(r"(#|//|;).*$")


def _strip_comment(line: str) -> str:
    return _COMMENT_RE.sub("", line)


def _split_operands(text: str) -> list[str]:
    if not text.strip():
        return []
    return [p.strip() for p in text.split(",")]


def parse_source(text: str) -> list[SourceLine]:
    """Primeira etapa: quebra o fonte em linhas com labels e operandos."""
    out: list[SourceLine] = []
    for i, raw in enumerate(text.splitlines(), start=1):
        body = _strip_comment(raw).strip()
        sl = SourceLine(line_no=i, raw=raw)
        # pode haver vários labels na mesma linha: "a: b: addi ..."
        while True:
            m = re.match(r"^([A-Za-z_.$][\w.$]*)\s*:\s*(.*)$", body)
            if not m:
                break
            sl.labels.append(m.group(1))
            body = m.group(2).strip()
        if body:
            parts = body.split(None, 1)
            sl.mnemonic = parts[0].lower()
            sl.operands = _split_operands(parts[1]) if len(parts) > 1 else []
        if sl.labels or sl.mnemonic:
            out.append(sl)
    return out


# --------------------------------------------------------------------------
# Expansão de pseudo-instruções
# --------------------------------------------------------------------------

def _li_parts(value: int) -> list[tuple[str, list[str]]]:
    """Expande `li` em addi ou lui+addi, conforme a magnitude."""
    v = value & 0xFFFFFFFF
    signed = v - (1 << 32) if v & 0x80000000 else v
    if -2048 <= signed <= 2047:
        return [("addi", ["{rd}", "x0", str(signed)])]
    lo = v & 0xFFF
    if lo >= 0x800:
        lo -= 0x1000
    hi = ((v - (lo & 0xFFFFFFFF)) >> 12) & 0xFFFFF
    parts = [("lui", ["{rd}", str(hi)])]
    if lo != 0:
        parts.append(("addi", ["{rd}", "{rd}", str(lo)]))
    return parts


# pseudo -> número de instruções reais quando o tamanho é fixo
_FIXED_PSEUDO_SIZE = {
    "nop": 1, "mv": 1, "not": 1, "neg": 1, "seqz": 1, "snez": 1,
    "sltz": 1, "sgtz": 1, "j": 1, "jr": 1, "ret": 1, "jal_label": 1,
    "beqz": 1, "bnez": 1, "blez": 1, "bgez": 1, "bltz": 1, "bgtz": 1,
    "bgt": 1, "ble": 1, "bgtu": 1, "bleu": 1,
    "la": 2, "call": 1, "tail": 1,
}


def _instruction_size(sl: SourceLine, symbols_known: bool = False) -> int:
    m = sl.mnemonic
    if m is None:
        return 0
    if m == ".word":
        return WORD_BYTES * max(1, len(sl.operands))
    if m == ".zero":
        n = _eval_int(sl.operands[0]) if sl.operands else 0
        return WORD_BYTES * n
    if m == "li":
        # tamanho depende do valor; avaliável já no primeiro passe pois
        # `li` só aceita constante, nunca label
        try:
            val = _eval_int(sl.operands[1])
        except Exception as e:  # noqa: BLE001
            raise AssemblyError(
                "`li` aceita apenas constante numérica", sl.line_no, sl.raw
            ) from e
        return WORD_BYTES * len(_li_parts(val))
    if m in _FIXED_PSEUDO_SIZE:
        return WORD_BYTES * _FIXED_PSEUDO_SIZE[m]
    return WORD_BYTES


def _eval_int(token: str) -> int:
    t = token.strip()
    neg = False
    if t.startswith("-"):
        neg, t = True, t[1:].strip()
    elif t.startswith("+"):
        t = t[1:].strip()
    try:
        if t.lower().startswith("0x"):
            v = int(t, 16)
        elif t.lower().startswith("0b"):
            v = int(t, 2)
        elif t.startswith("0o"):
            v = int(t, 8)
        else:
            v = int(t, 10)
    except ValueError as e:
        raise AssemblyError(f"constante numérica inválida: {token!r}") from e
    return -v if neg else v


# --------------------------------------------------------------------------
# Montador
# --------------------------------------------------------------------------

class Assembler:
    """Montador de dois passes.

    `allow_m=False` rejeita instruções da extensão M, o que é usado para
    garantir que os programas de baseline usam somente RV32I (FR-RV-19).
    """

    def __init__(self, base_address: int = 0, allow_m: bool = True,
                 allow_unsupported: bool = False):
        self.base_address = base_address
        self.allow_m = allow_m
        self.allow_unsupported = allow_unsupported
        self.symbols: dict[str, int] = {}

    # -- passe 1 ----------------------------------------------------------
    def _first_pass(self, lines: list[SourceLine]) -> None:
        addr = self.base_address
        for sl in lines:
            for lab in sl.labels:
                if lab in self.symbols:
                    raise AssemblyError(f"label duplicado: {lab!r}", sl.line_no, sl.raw)
                self.symbols[lab] = addr
            try:
                sl.address = addr
                sl.size = _instruction_size(sl)
            except AssemblyError as e:
                if e.line_no is None:
                    raise AssemblyError(str(e), sl.line_no, sl.raw) from e
                raise
            addr += sl.size

    # -- resolução de operandos -------------------------------------------
    def _resolve(self, token: str, pc: int) -> int:
        """Constante numérica ou label (retorna endereço absoluto)."""
        t = token.strip()
        if t == ".":
            return pc
        if re.fullmatch(r"[A-Za-z_.$][\w.$]*", t) and t.lower() not in ("x0",):
            if t not in self.symbols:
                raise AssemblyError(f"label não definido: {t!r}")
            return self.symbols[t]
        return _eval_int(t)

    def _branch_offset(self, token: str, pc: int) -> int:
        target = self._resolve(token, pc)
        # se for label, o alvo é absoluto; se for número, tratamos como
        # deslocamento já relativo somente quando não houver label
        if re.fullmatch(r"[A-Za-z_.$][\w.$]*", token.strip()) or token.strip() == ".":
            off = target - pc
        else:
            off = target
        if off % 2 != 0:
            raise AssemblyError(f"deslocamento de branch/jump ímpar: {off}")
        return off

    def _mem_operand(self, token: str) -> tuple[int, int]:
        """`imm(rs1)` -> (imm, rs1). Aceita `(rs1)` como imm 0."""
        m = re.fullmatch(r"\s*([^()]*)\(\s*([^()]+?)\s*\)\s*", token)
        if not m:
            raise AssemblyError(f"operando de memória inválido: {token!r} (esperado imm(rs))")
        imm_txt = m.group(1).strip()
        rs1 = parse_register(m.group(2))
        imm = 0
        if imm_txt:
            imm = self._resolve(imm_txt, 0)
        return imm, rs1

    # -- passe 2 ----------------------------------------------------------
    def _encode_line(self, sl: SourceLine) -> list[int]:
        m, ops, pc = sl.mnemonic, sl.operands, sl.address
        assert m is not None

        def need(n: int) -> None:
            if len(ops) != n:
                raise AssemblyError(f"`{m}` espera {n} operando(s), recebeu {len(ops)}")

        # ---- diretivas ----
        if m == ".word":
            if not ops:
                raise AssemblyError("`.word` sem valor")
            return [self._resolve(o, pc) & 0xFFFFFFFF for o in ops]
        if m == ".zero":
            need(1)
            return [0] * _eval_int(ops[0])
        if m in (".text", ".globl", ".global", ".align", ".type", ".section", ".option"):
            return []  # aceitas e ignoradas

        # ---- instruções não implementadas pela CPU alvo ----
        if m in UNSUPPORTED_BY_CPU:
            if not self.allow_unsupported:
                raise AssemblyError(
                    f"`{m}` não é implementada pela CPU alvo "
                    f"(ver specs/decisions.md, ADR-000); use allow_unsupported=True "
                    f"apenas para testar o caminho de instrução inválida"
                )
            if m == "ecall":
                return [enc_i(0, 0, 0, 0, 0b1110011)]
            if m == "ebreak":
                return [enc_i(1, 0, 0, 0, 0b1110011)]
            return [enc_i(0, 0, 0, 0, 0b0001111)]

        # ---- extensão M ----
        if m in M_TYPE:
            if not self.allow_m:
                raise AssemblyError(
                    f"`{m}` é RV32M e este programa foi montado como RV32I puro "
                    f"(FR-RV-19)"
                )
            need(3)
            rd, rs1, rs2 = (parse_register(o) for o in ops)
            return [enc_r(FUNCT7_M, rs2, rs1, M_TYPE[m], rd, OPCODE_OP)]

        # ---- R-type ----
        if m in R_TYPE:
            need(3)
            f3, f7 = R_TYPE[m]
            rd, rs1, rs2 = (parse_register(o) for o in ops)
            return [enc_r(f7, rs2, rs1, f3, rd, OPCODE_OP)]

        # ---- I-type aritmético ----
        if m in I_TYPE_ARITH:
            need(3)
            rd, rs1 = parse_register(ops[0]), parse_register(ops[1])
            imm = _check_signed(self._resolve(ops[2], pc), 12, f"imediato de `{m}`")
            return [enc_i(imm, rs1, I_TYPE_ARITH[m], rd, OPCODE_OP_IMM)]

        # ---- shifts imediatos ----
        if m in I_TYPE_SHIFT:
            need(3)
            f3, f7 = I_TYPE_SHIFT[m]
            rd, rs1 = parse_register(ops[0]), parse_register(ops[1])
            shamt = _check_unsigned(self._resolve(ops[2], pc), 5, f"shamt de `{m}`")
            return [enc_i((f7 << 5) | shamt, rs1, f3, rd, OPCODE_OP_IMM)]

        # ---- loads ----
        if m in LOADS:
            need(2)
            rd = parse_register(ops[0])
            imm, rs1 = self._mem_operand(ops[1])
            imm = _check_signed(imm, 12, f"offset de `{m}`")
            return [enc_i(imm, rs1, LOADS[m], rd, OPCODE_LOAD)]

        # ---- stores ----
        if m in STORES:
            need(2)
            rs2 = parse_register(ops[0])
            imm, rs1 = self._mem_operand(ops[1])
            imm = _check_signed(imm, 12, f"offset de `{m}`")
            return [enc_s(imm, rs2, rs1, STORES[m], OPCODE_STORE)]

        # ---- branches ----
        if m in BRANCHES:
            need(3)
            rs1, rs2 = parse_register(ops[0]), parse_register(ops[1])
            off = self._branch_offset(ops[2], pc)
            off = _check_signed(off, 13, f"deslocamento de `{m}`")
            return [enc_b(off, rs2, rs1, BRANCHES[m], OPCODE_BRANCH)]

        # ---- U-type ----
        if m in ("lui", "auipc"):
            need(2)
            rd = parse_register(ops[0])
            imm = _check_unsigned(self._resolve(ops[1], pc) & 0xFFFFF, 20,
                                  f"imediato de `{m}`")
            return [enc_u(imm, rd, OPCODE_LUI if m == "lui" else OPCODE_AUIPC)]

        # ---- jal / jalr ----
        if m == "jal":
            if len(ops) == 1:                     # jal label  => rd = ra
                rd, target = 1, ops[0]
            elif len(ops) == 2:
                rd, target = parse_register(ops[0]), ops[1]
            else:
                raise AssemblyError("`jal` espera 1 ou 2 operandos")
            off = _check_signed(self._branch_offset(target, pc), 21,
                                "deslocamento de `jal`")
            return [enc_j(off, rd, OPCODE_JAL)]

        if m == "jalr":
            if len(ops) == 1:                     # jalr rs => jalr ra, 0(rs)
                return [enc_i(0, parse_register(ops[0]), 0, 1, OPCODE_JALR)]
            if len(ops) == 2:                     # jalr rd, imm(rs)
                rd = parse_register(ops[0])
                imm, rs1 = self._mem_operand(ops[1])
                return [enc_i(_check_signed(imm, 12, "offset de `jalr`"), rs1, 0, rd,
                              OPCODE_JALR)]
            if len(ops) == 3:                     # jalr rd, rs, imm
                rd, rs1 = parse_register(ops[0]), parse_register(ops[1])
                imm = _check_signed(self._resolve(ops[2], pc), 12, "offset de `jalr`")
                return [enc_i(imm, rs1, 0, rd, OPCODE_JALR)]
            raise AssemblyError("`jalr` com número de operandos inválido")

        # ---- pseudo-instruções ----
        return self._encode_pseudo(sl)

    def _encode_pseudo(self, sl: SourceLine) -> list[int]:
        m, ops, pc = sl.mnemonic, sl.operands, sl.address
        R = parse_register

        def sub(mn: str, o: list[str]) -> list[int]:
            clone = SourceLine(sl.line_no, sl.raw, [], mn, o, pc, WORD_BYTES)
            return self._encode_line(clone)

        if m == "nop":
            return sub("addi", ["x0", "x0", "0"])
        if m == "mv":
            return sub("addi", [ops[0], ops[1], "0"])
        if m == "not":
            return sub("xori", [ops[0], ops[1], "-1"])
        if m == "neg":
            return sub("sub", [ops[0], "x0", ops[1]])
        if m == "seqz":
            return sub("sltiu", [ops[0], ops[1], "1"])
        if m == "snez":
            return sub("sltu", [ops[0], "x0", ops[1]])
        if m == "sltz":
            return sub("slt", [ops[0], ops[1], "x0"])
        if m == "sgtz":
            return sub("slt", [ops[0], "x0", ops[1]])
        if m == "li":
            out: list[int] = []
            for mn, tmpl in _li_parts(_eval_int(ops[1])):
                out += sub(mn, [t.replace("{rd}", ops[0]) for t in tmpl])
            return out
        if m == "la":
            # auipc + addi, PC-relativo (2 instruções)
            target = self._resolve(ops[1], pc)
            delta = target - pc
            lo = delta & 0xFFF
            if lo >= 0x800:
                lo -= 0x1000
            hi = ((delta - lo) >> 12) & 0xFFFFF
            rd = R(ops[0])
            return [enc_u(hi, rd, OPCODE_AUIPC), enc_i(lo & 0xFFF, rd, 0, rd,
                                                       OPCODE_OP_IMM)]
        if m == "j":
            off = _check_signed(self._branch_offset(ops[0], pc), 21, "deslocamento de `j`")
            return [enc_j(off, 0, OPCODE_JAL)]
        if m == "call":
            off = _check_signed(self._branch_offset(ops[0], pc), 21,
                                "deslocamento de `call`")
            return [enc_j(off, 1, OPCODE_JAL)]
        if m == "tail":
            off = _check_signed(self._branch_offset(ops[0], pc), 21,
                                "deslocamento de `tail`")
            return [enc_j(off, 0, OPCODE_JAL)]
        if m == "jr":
            return [enc_i(0, R(ops[0]), 0, 0, OPCODE_JALR)]
        if m == "ret":
            return [enc_i(0, 1, 0, 0, OPCODE_JALR)]
        if m in ("beqz", "bnez", "blez", "bgez", "bltz", "bgtz"):
            base = {"beqz": ("beq", False), "bnez": ("bne", False),
                    "blez": ("bge", True), "bgez": ("bge", False),
                    "bltz": ("blt", False), "bgtz": ("blt", True)}[m]
            real, swap = base
            rs = ops[0]
            return sub(real, ["x0", rs, ops[1]] if swap else [rs, "x0", ops[1]])
        if m in ("bgt", "ble", "bgtu", "bleu"):
            real = {"bgt": "blt", "ble": "bge", "bgtu": "bltu", "bleu": "bgeu"}[m]
            return sub(real, [ops[1], ops[0], ops[2]])

        raise AssemblyError(f"instrução desconhecida: {m!r}")

    # -- API --------------------------------------------------------------
    def assemble(self, text: str) -> list[int]:
        lines = parse_source(text)
        self.symbols = {}
        self._first_pass(lines)
        words: list[int] = []
        for sl in lines:
            if sl.mnemonic is None:
                continue
            expected = len(words) * WORD_BYTES + self.base_address
            if sl.address != expected:
                raise AssemblyError(
                    f"inconsistência interna de endereço: esperado {expected:#x}, "
                    f"calculado {sl.address:#x}", sl.line_no, sl.raw
                )
            try:
                words += self._encode_line(sl)
            except AssemblyError as e:
                if e.line_no is None:
                    raise AssemblyError(str(e), sl.line_no, sl.raw) from e
                raise
        return words


def assemble(text: str, base_address: int = 0, allow_m: bool = True,
             allow_unsupported: bool = False) -> list[int]:
    """Monta um fonte e devolve a lista de palavras de 32 bits."""
    return Assembler(base_address, allow_m, allow_unsupported).assemble(text)


def assemble_with_symbols(text: str, base_address: int = 0, allow_m: bool = True,
                          allow_unsupported: bool = False
                          ) -> tuple[list[int], dict[str, int]]:
    """Como `assemble`, mas também devolve a tabela de símbolos.

    A tabela é usada pelo testbench para saber o endereço do auto-laço de
    parada, o que permite detectar término de forma determinística
    (FR-RV-21). Isso é necessário porque a CPU resolve saltos no estágio EX:
    num auto-laço o PC não fica parado, ele oscila entre o endereço do salto
    e os dois seguintes, que são descartados por flush.
    """
    a = Assembler(base_address, allow_m, allow_unsupported)
    words = a.assemble(text)
    return words, dict(a.symbols)


# Auto-laços: `JAL x0, 0` e `BEQ x0, x0, 0`. Ambos saltam para si mesmos
# independentemente do endereço, por isso podem ser localizados na imagem.
SELF_LOOP_ENCODINGS = (0x0000006F, 0x00000063)


def find_halt_addresses(words: list[int], base_address: int = 0) -> list[int]:
    """Endereços de byte de todas as instruções de auto-laço da imagem.

    REQ: FR-RV-08 (convenção de parada documentada), FR-RV-21 (término
    determinístico).
    """
    return [base_address + 4 * i
            for i, w in enumerate(words)
            if (w & 0xFFFFFFFF) in SELF_LOOP_ENCODINGS]


# --------------------------------------------------------------------------
# Imagem .ram  (formato definido em specs/decisions.md, ADR-003)
# --------------------------------------------------------------------------
# REQ: FR-RV-08 (formato documentado), FR-RV-09 (consumido pela ROM)

def write_ram_image(words: list[int], path: str | Path,
                    header: str | None = None) -> Path:
    """Grava a imagem `.ram`: uma palavra de 32 bits por linha, 8 dígitos hex.

    A linha de índice 0 corresponde ao endereço de byte 0x00000000 e a linha
    `n` ao endereço `4*n`.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    if header:
        for h in header.strip().splitlines():
            lines.append(f"# {h.strip()}")
    for w in words:
        lines.append(f"{w & 0xFFFFFFFF:08x}")
    p.write_text("\n".join(lines) + "\n", encoding="ascii")
    return p


def read_ram_image(path: str | Path) -> list[int]:
    """Lê uma imagem `.ram`. Ignora linhas vazias e comentários `#`."""
    words: list[int] = []
    for line_no, raw in enumerate(Path(path).read_text(encoding="ascii").splitlines(), 1):
        s = raw.split("#", 1)[0].strip()
        if not s:
            continue
        if not re.fullmatch(r"[0-9a-fA-F]{1,8}", s):
            raise AssemblyError(
                f"linha inválida na imagem .ram: {raw!r} "
                f"(esperado até 8 dígitos hexadecimais)", line_no
            )
        words.append(int(s, 16))
    return words


def disassemble_word(word: int) -> str:
    """Descrição mínima para mensagens de erro de teste (não é disassembler completo)."""
    opcode = word & 0x7F
    names = {
        OPCODE_LUI: "LUI", OPCODE_AUIPC: "AUIPC", OPCODE_JAL: "JAL",
        OPCODE_JALR: "JALR", OPCODE_BRANCH: "BRANCH", OPCODE_LOAD: "LOAD",
        OPCODE_STORE: "STORE", OPCODE_OP_IMM: "OP-IMM", OPCODE_OP: "OP",
    }
    base = names.get(opcode, f"opcode={opcode:#09b}")
    if opcode == OPCODE_OP and ((word >> 25) & 0x7F) == FUNCT7_M:
        f3 = (word >> 12) & 0x7
        inv = {v: k for k, v in M_TYPE.items()}
        base = f"OP/M:{inv.get(f3, f3).upper()}"
    return f"{word:#010x} ({base})"
