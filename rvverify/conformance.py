#!/usr/bin/env python3
"""Suite de conformidade: o que uma CPU precisa passar para valer como RV32I(M).

REQ: FR-RV-03 (ISA estritamente RISC-V), FR-RV-04, FR-RV-11 (baseline antes da
extensao), FR-RV-13 (as oito instrucoes M), FR-RV-14 (casos especiais),
FR-RV-16 (RV32I e RV32IM da mesma base), FR-RV-21, FR-RV-22, FR-RV-23
(modelo de referencia), FR-RV-26 (validacao por manifesto), FR-RV-27
(veredito), FR-RV-28 (diagnostico), FR-RV-29 (eventos e log por caso),
NFR-RV-02 (nada declarado sem medir).

Esta suite nao conhece CPU nenhuma. Tudo o que ela sabe sobre o design vem do
`cpu.toml`. Roda igual na CPU pipeline de 5 estagios e na monociclo escrita do
zero -- e e exatamente essa a prova de que o validador julga o COMPORTAMENTO da
CPU, e nao o formato dela.

## Duas etapas, nessa ordem

1. **RV32I** -- com a extensao M DESLIGADA. Se esta etapa falhar, a etapa 2 nem
   roda: nao faz sentido cobrar a extensao de uma CPU cuja base esta quebrada, e
   um erro na base apareceria como se fosse da extensao (FR-RV-11).
2. **RV32IM** -- ligando o generic declarado em `[design].rv32m_generic`.
   Ausente esse campo, a etapa e PULADA e reportada como pulada -- nunca como
   aprovada.

## De onde vem o valor esperado

Sempre do modelo de referencia em Python (`rvverify/reference.py`), nunca de
constante escrita a mao. Se o modelo e o hardware discordarem, o relatorio
mostra os dois valores lado a lado.

## Veredito (FR-RV-27)

`aprovado` so quando a suite INTEIRA rodou e passou; `reprovado` com qualquer
caso falho; `incompleto` com etapa pulada; `parcial` quando o usuario pediu so
parte da suite. O builder e importado sob demanda: o catalogo e o veredito
funcionam sem cocotb instalado.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import feedback
from ._ferramentas import REPO_ROOT, ref
from .manifest import CpuManifest, load_manifest

from .asm import (
    AssemblyError,
    assemble_with_symbols,
    find_halt_addresses,
    write_ram_image,
)

__all__ = ["Case", "CaseResult", "build_cases", "catalog", "run_conformance",
           "veredito", "exit_code_for", "resolve_selection", "SelectionError",
           "STAGES", "REPO_ROOT"]

STAGES = ("rv32i", "rv32m")
EventSink = Callable[[dict], None]

MASK32 = 0xFFFFFFFF
HALT = "halt:\n    j halt\n"

# Subconjunto dos valores de borda. A varredura completa de 169 pares por
# instrucao vive na suite dedicada da CPU pipeline; aqui o objetivo e um
# veredito rapido e honesto sobre uma CPU recem-entregue, entao usamos os
# valores que quebram implementacao errada com mais frequencia.
EDGE = [0x00000000, 0x00000001, 0xFFFFFFFF, 0x7FFFFFFF, 0x80000000,
        0x00000002, 0xFFFFFFFE, 0x12345678, 0xDEADBEEF]


def sig(value: int) -> str:
    """Literal decimal com sinal -- o unico formato que o `li` aceita."""
    v = value & MASK32
    return str(v - (1 << 32) if v & 0x80000000 else v)


@dataclass
class Case:
    """Um caso de conformidade: um programa e o que ele deve publicar."""

    name: str
    asm: str
    expect_ram: dict[int, int]
    requirements: list[str]
    stage: str                              # "rv32i" | "rv32m"
    max_cycles: int = 20000
    expect_regs: dict[int, int] = field(default_factory=dict)
    description: str = ""
    # endereco de RAM -> o que produziu aquele valor (para o diagnostico)
    labels: dict[int, str] = field(default_factory=dict)
    # operacao binaria: os pares de entrada, na ordem dos slots de RAM
    pairs: list[tuple[int, int]] | None = None

    @property
    def id(self) -> str:
        return f"{self.stage}/{self.name}"

    def plan_entry(self) -> dict:
        """O caso como aparece no plano de execucao (FR-RV-29)."""
        return {
            "id": self.id,
            "grupo": "conformidade",
            "etapa": self.stage,
            "nome": self.name,
            "requisitos": list(self.requirements),
            "descricao": self.description,
        }


@dataclass
class CaseResult:
    name: str
    stage: str
    passed: bool
    requirements: list[str]
    detail: str = ""
    cycles: int | None = None
    instructions: int | None = None
    cpi: float | None = None
    m_instructions: int | None = None
    id: str = ""
    description: str = ""
    stalls: int | None = None
    flushes: int | None = None
    duration_s: float | None = None
    log: str | None = None
    diagnostico: dict | None = None


# --------------------------------------------------------------------------
# Construtores de programa
# --------------------------------------------------------------------------

def _slots(base: int, values: list[int]) -> dict[int, int]:
    return {base + 4 * i: v & MASK32 for i, v in enumerate(values)}


def _labels(base: int, texts: list[str]) -> dict[int, str]:
    return {base + 4 * i: t for i, t in enumerate(texts)}


def _binop_program(mnemonic: str, pairs: list[tuple[int, int]], base: int) -> str:
    """Aplica `mnemonic` a cada par e publica o resultado num slot de RAM."""
    lines = [f"# conformidade: {mnemonic}", f"    li   x18, {base}"]
    for i, (a, b) in enumerate(pairs):
        lines += [
            f"    li   x10, {sig(a)}",
            f"    li   x11, {sig(b)}",
            f"    {mnemonic:<6} x12, x10, x11",
            f"    sw   x12, {4 * i}(x18)",
        ]
    lines.append(HALT)
    return "\n".join(lines)


def _binop_case(mnemonic: str, pairs: list[tuple[int, int]], base: int,
                stage: str, apply, reqs: list[str]) -> Case:
    return Case(
        name=mnemonic,
        asm=_binop_program(mnemonic, pairs, base),
        expect_ram=_slots(base, [apply(mnemonic, a, b) for a, b in pairs]),
        requirements=reqs,
        stage=stage,
        description=f"{mnemonic.upper()} sobre {len(pairs)} pares de valores de borda",
        labels=_labels(base, [f"{mnemonic}({feedback.hexw(a)}, {feedback.hexw(b)})"
                              for a, b in pairs]),
        pairs=list(pairs),
    )


def _pairs() -> list[tuple[int, int]]:
    """Pares de borda, limitados para caber na RAM e na ROM."""
    out = [(a, b) for a in EDGE for b in EDGE]
    return out[:64]          # 64 slots = 256 bytes, metade da RAM de 512


# --------------------------------------------------------------------------
# Os casos
# --------------------------------------------------------------------------

I_BINOPS = ["add", "sub", "and", "or", "xor", "sll", "srl", "sra", "slt", "sltu"]
M_BINOPS = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]
I_IMMOPS = ["addi", "andi", "ori", "xori", "slti", "sltiu",
            "slli", "srli", "srai"]


def _signed(value: int) -> int:
    value &= MASK32
    return value - (1 << 32) if value & 0x80000000 else value


def _imm_result(op: str, value: int, immediate: int) -> int:
    """Modelo independente das nove formas de operação com imediato."""
    imm = immediate & 0xFFF
    if imm & 0x800:
        imm -= 0x1000
    if op == "addi":
        return (value + imm) & MASK32
    if op == "andi":
        return value & imm
    if op == "ori":
        return value | (imm & MASK32)
    if op == "xori":
        return value ^ (imm & MASK32)
    if op == "slti":
        return int(_signed(value) < imm)
    if op == "sltiu":
        return int((value & MASK32) < (imm & MASK32))
    shift = immediate & 0x1F
    if op == "slli":
        return (value << shift) & MASK32
    if op == "srli":
        return (value & MASK32) >> shift
    if op == "srai":
        return (_signed(value) >> shift) & MASK32
    raise ValueError(f"imediato desconhecido: {op}")


def _imm_case(op: str, base: int, stage: str) -> Case:
    immediates = (0, 1, 5, 12, 31) if op in {"slli", "srli", "srai"} \
        else (0, 1, 5, 12, 31, -1)
    pairs = [(v, i) for v in EDGE[:8] for i in immediates]
    pairs = pairs[:48]
    lines = [f"# conformidade: {op}", f"    li x18, {base}"]
    for i, (value, immediate) in enumerate(pairs):
        lines += [f"    li x10, {sig(value)}",
                  f"    {op} x12, x10, {immediate}",
                  f"    sw x12, {4 * i}(x18)"]
    lines.append(HALT)
    return Case(
        name=op,
        asm="\n".join(lines),
        expect_ram=_slots(base, [_imm_result(op, v, i) for v, i in pairs]),
        requirements=["FR-RV-04", "FR-RV-22"],
        stage=stage,
        description=f"{op.upper()} sobre {len(pairs)} valores e imediatos de borda",
        labels=_labels(base, [f"{op}({feedback.hexw(v)}, {i})" for v, i in pairs]),
    )


def build_cases(base: int) -> list[Case]:
    """Todos os casos de conformidade, ja com o esperado do modelo."""
    cases: list[Case] = []

    # ---------------- etapa 1: RV32I ----------------
    for op in I_BINOPS:
        cases.append(_binop_case(op, _pairs(), base, "rv32i",
                                 ref.apply_i, ["FR-RV-04", "FR-RV-22"]))
    for op in I_IMMOPS:
        cases.append(_imm_case(op, base, "rv32i"))

    cases.append(Case(
        name="x0_imutavel",
        stage="rv32i",
        requirements=["FR-RV-04"],
        description="x0 le zero e descarta escrita",
        asm=f"""
# x0 le zero e descarta escrita (FR-RV-04)
    li   x18, {base}
    addi x0, x0, 123
    sw   x0, 0(x18)
    add  x5, x0, x0
    sw   x5, 4(x18)
    li   x6, -1
    add  x7, x6, x0
    sw   x7, 8(x18)
{HALT}""",
        expect_ram=_slots(base, [0, 0, 0xFFFFFFFF]),
        labels=_labels(base, ["x0 depois de addi x0, x0, 123",
                              "add x5, x0, x0",
                              "add x7, x6 (= -1), x0"]),
        max_cycles=500,
    ))

    cases.append(Case(
        name="load_store_larguras",
        stage="rv32i",
        requirements=["FR-RV-04", "FR-RV-05"],
        description="LB/LBU/LH/LHU/LW e SB/SH/SW: largura e extensao de sinal",
        asm=f"""
# sw/lw, sb/lb/lbu, sh/lh/lhu -- extensao de sinal importa
    li   x18, {base}
    addi x19, x18, 64
    li   x10, -1412567296          # 0xABCDEF00
    sw   x10, 0(x19)
    lw   x11, 0(x19)
    sw   x11, 0(x18)
    li   x12, -2                   # 0xFE
    sb   x12, 16(x19)
    lb   x13, 16(x19)              # sinal  -> 0xFFFFFFFE
    sw   x13, 4(x18)
    lbu  x14, 16(x19)              # zero   -> 0x000000FE
    sw   x14, 8(x18)
    li   x15, -2                   # 0xFFFE
    sh   x15, 20(x19)
    lh   x16, 20(x19)              # sinal  -> 0xFFFFFFFE
    sw   x16, 12(x18)
    lhu  x17, 20(x19)              # zero   -> 0x0000FFFE
    sw   x17, 16(x18)
{HALT}""",
        expect_ram=_slots(base, [0xABCDEF00, 0xFFFFFFFE, 0x000000FE,
                                 0xFFFFFFFE, 0x0000FFFE]),
        labels=_labels(base, ["lw de 0xabcdef00",
                              "lb de 0xfe (com sinal)",
                              "lbu de 0xfe (sem sinal)",
                              "lh de 0xfffe (com sinal)",
                              "lhu de 0xfffe (sem sinal)"]),
        max_cycles=800,
    ))

    cases.append(Case(
        name="branches",
        stage="rv32i",
        requirements=["FR-RV-04", "FR-RV-22"],
        description="Os seis branches, tomados e nao tomados",
        asm=f"""
# os seis branches, cada um com o caso tomado e o nao tomado
    li   x18, {base}
    li   x5, -1
    li   x6, 1
    li   x20, 0
    beq  x5, x5, b1
    addi x20, x20, 1            # pulada
b1: bne  x5, x6, b2
    addi x20, x20, 2            # pulada
b2: blt  x5, x6, b3             # -1 < 1 com sinal
    addi x20, x20, 4            # pulada
b3: bltu x6, x5, b4             # 1 <u 0xFFFFFFFF
    addi x20, x20, 8            # pulada
b4: bge  x6, x5, b5
    addi x20, x20, 16           # pulada
b5: bgeu x5, x6, b6
    addi x20, x20, 32           # pulada
b6: sw   x20, 0(x18)            # zero se todos foram tomados
    li   x21, 0
    beq  x5, x6, n1             # NAO tomado
    addi x21, x21, 7
n1: sw   x21, 4(x18)            # 7 se o nao-tomado nao desviou
{HALT}""",
        expect_ram=_slots(base, [0, 7]),
        labels=_labels(base, [
            "soma das instrucoes que deviam ser puladas (1=beq 2=bne 4=blt "
            "8=bltu 16=bge 32=bgeu)",
            "7 se o beq nao tomado seguiu em frente"]),
        max_cycles=800,
    ))

    jal_asm = f"""
# JAL guarda o retorno, JALR volta; LUI e AUIPC formam constantes
    li   x18, {base}
    li   x20, 0
    jal  x1, sub_rotina
    addi x20, x20, 1            # executa DEPOIS do ret
    sw   x20, 0(x18)
    lui  x21, 0xABCDE
    sw   x21, 4(x18)
aui:
    auipc x22, 0x12
    sw   x22, 8(x18)
    j    fim
sub_rotina:
    addi x20, x20, 10
    jalr x0, 0(x1)
fim:
{HALT}"""
    # o valor de AUIPC depende do endereco da instrucao: vem do proprio montador
    _, jal_symbols = assemble_with_symbols(jal_asm, base_address=0, allow_m=False)
    aui_pc = jal_symbols["aui"]
    cases.append(Case(
        name="jal_jalr_lui_auipc",
        stage="rv32i",
        requirements=["FR-RV-04"],
        description="JAL/JALR com retorno, LUI e AUIPC",
        asm=jal_asm,
        expect_ram=_slots(base, [11, 0xABCDE000, aui_pc + (0x12 << 12)]),
        labels=_labels(base, ["10 da sub-rotina + 1 depois do retorno (jal/jalr)",
                              "lui x21, 0xabcde",
                              f"auipc x22, 0x12 em {feedback.hexw(aui_pc)}"]),
        max_cycles=800,
    ))

    soma = sum(range(1, 11))
    cases.append(Case(
        name="laco_com_dependencia",
        stage="rv32i",
        requirements=["FR-RV-22"],
        description="Laco com dependencia entre instrucoes (soma de 1 a 10)",
        asm=f"""
# laco com dependencia entre instrucoes e branch de controle
    li   x18, {base}
    li   x5, 0
    li   x6, 1
    li   x7, 11
loop:
    bge  x6, x7, fim
    add  x5, x5, x6
    addi x6, x6, 1
    j    loop
fim:
    sw   x5, 0(x18)
{HALT}""",
        expect_ram=_slots(base, [soma]),
        labels=_labels(base, ["soma de 1 a 10 acumulada no laco"]),
        max_cycles=2000,
    ))

    # ---------------- etapa 2: RV32M ----------------
    for op in M_BINOPS:
        cases.append(_binop_case(op, _pairs(), base, "rv32m",
                                 ref.apply_m, ["FR-RV-13", "FR-RV-22"]))

    x = 0x12345678
    cases.append(Case(
        name="divisao_por_zero",
        stage="rv32m",
        requirements=["FR-RV-14"],
        description="Divisao por zero sem trap: valores definidos pela especificacao",
        asm=f"""
# RISC-V NAO gera trap em divisao por zero: valor definido, execucao segue
    li   x18, {base}
    li   x10, {sig(x)}
    li   x11, 0
    div  x12, x10, x11
    sw   x12, 0(x18)
    divu x13, x10, x11
    sw   x13, 4(x18)
    rem  x14, x10, x11
    sw   x14, 8(x18)
    remu x15, x10, x11
    sw   x15, 12(x18)
    addi x16, x0, 1234          # a CPU tem de continuar executando
    sw   x16, 16(x18)
{HALT}""",
        expect_ram=_slots(base, [ref.div(x, 0), ref.divu(x, 0),
                                 ref.rem(x, 0), ref.remu(x, 0), 1234]),
        labels=_labels(base, ["div 0x12345678 / 0", "divu 0x12345678 / 0",
                              "rem 0x12345678 % 0", "remu 0x12345678 % 0",
                              "addi depois das divisoes (a CPU seguiu executando)"]),
        max_cycles=800,
    ))

    lo = 0x80000000
    cases.append(Case(
        name="overflow_da_divisao",
        stage="rv32m",
        requirements=["FR-RV-14"],
        description="(-2^31) / (-1): overflow sem trap",
        asm=f"""
# (-2^31)/(-1) nao e representavel: a spec manda envolver, nao trapar
    li   x18, {base}
    li   x10, {sig(lo)}
    li   x11, -1
    div  x12, x10, x11
    sw   x12, 0(x18)
    rem  x13, x10, x11
    sw   x13, 4(x18)
    divu x14, x10, x11
    sw   x14, 8(x18)
    remu x15, x10, x11
    sw   x15, 12(x18)
{HALT}""",
        expect_ram=_slots(base, [ref.div(lo, 0xFFFFFFFF), ref.rem(lo, 0xFFFFFFFF),
                                 ref.divu(lo, 0xFFFFFFFF), ref.remu(lo, 0xFFFFFFFF)]),
        labels=_labels(base, ["div 0x80000000 / -1", "rem 0x80000000 % -1",
                              "divu 0x80000000 / 0xffffffff",
                              "remu 0x80000000 % 0xffffffff"]),
        max_cycles=800,
    ))

    n = 10
    total = 0
    for i in range(1, n + 1):
        total = ref.add(total, ref.mul(i, i))
    cases.append(Case(
        name="misto_rv32i_rv32m",
        stage="rv32m",
        requirements=["FR-RV-12", "FR-RV-22"],
        description="RV32I e RV32M no mesmo fluxo: laco, load/store, MUL, DIV e REM",
        asm=f"""
# RV32I e RV32M no mesmo fluxo: laco, load/store, branch, MUL, DIV e REM
    li   x18, {base}
    addi x19, x18, 64
    li   x6, 1
    li   x7, {n + 1}
fill:
    bge  x6, x7, meio
    mul  x8, x6, x6
    addi x20, x6, -1
    slli x20, x20, 2
    add  x21, x19, x20
    sw   x8, 0(x21)
    addi x6, x6, 1
    j    fill
meio:
    li   x5, 0
    li   x6, 0
    li   x7, {n}
soma:
    bge  x6, x7, fim
    slli x20, x6, 2
    add  x21, x19, x20
    lw   x22, 0(x21)
    add  x5, x5, x22
    addi x6, x6, 1
    j    soma
fim:
    sw   x5, 0(x18)
    li   x9, 7
    div  x10, x5, x9
    sw   x10, 4(x18)
    rem  x11, x5, x9
    sw   x11, 8(x18)
{HALT}""",
        expect_ram=_slots(base, [total, ref.div(total, 7), ref.rem(total, 7)]),
        labels=_labels(base, ["soma de i*i para i de 1 a 10 (MUL, gravada e relida)",
                              "soma / 7 (DIV)", "soma % 7 (REM)"]),
        max_cycles=5000,
    ))

    return cases


# --------------------------------------------------------------------------
# Catalogo e selecao
# --------------------------------------------------------------------------

# O catalogo nao depende do mapa de memoria: nomes, etapas, requisitos e
# descricoes sao os mesmos para qualquer `ram_base`.
_CATALOG_BASE = 0x00FC8100


def catalog() -> list[dict]:
    """Os casos da suite, na ordem de execucao, sem rodar nada."""
    return [c.plan_entry() for c in build_cases(_CATALOG_BASE)]


class SelectionError(ValueError):
    """Um nome pedido em `--casos` nao existe na suite."""


def resolve_selection(names: list[str] | None) -> set[str] | None:
    """Traduz nomes (`sra`) ou ids (`rv32i/sra`) para ids de caso.

    None significa "a suite inteira". Nome desconhecido e erro, com a lista
    dos validos: selecionar nada em silencio produziria um PARCIAL vazio.
    """
    if not names:
        return None
    by_id = {c["id"]: c for c in catalog()}
    by_name = {c["nome"]: c["id"] for c in by_id.values()}
    chosen: set[str] = set()
    unknown: list[str] = []
    for raw in names:
        item = raw.strip()
        if not item:
            continue
        if item in by_id:
            chosen.add(item)
        elif item in by_name:
            chosen.add(by_name[item])
        else:
            unknown.append(item)
    if unknown:
        raise SelectionError(
            f"caso(s) desconhecido(s): {', '.join(unknown)}. Validos: "
            f"{', '.join(by_name)}"
        )
    return chosen


# --------------------------------------------------------------------------
# Veredito
# --------------------------------------------------------------------------

def veredito(results: list, skipped: list[str], *, complete: bool) -> str:
    """Os quatro estados de FR-RV-27, na ordem de precedencia.

    `complete` diz se a suite inteira foi pedida (as duas etapas, sem filtro
    de casos). Sem nenhum caso executado nao ha aprovacao possivel.
    """
    passed = [r["passed"] if isinstance(r, dict) else r.passed for r in results]
    if any(not p for p in passed):
        return "reprovado"
    if skipped or not passed:
        return "incompleto"
    if not complete:
        return "parcial"
    return "aprovado"


def exit_code_for(verdict: str) -> int:
    """FR-RV-27: exit code != 0 com caso reprovado ou etapa pulada."""
    return 0 if verdict in ("aprovado", "parcial") else 1


# --------------------------------------------------------------------------
# Execucao
# --------------------------------------------------------------------------

def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _read_text(path: Path, limit: int = 400_000) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-limit:]


def _failed(case: Case, started: float, diag: dict, log: Path | None = None,
            data: dict | None = None) -> CaseResult:
    data = data or {}
    return CaseResult(
        case.name, case.stage, False, case.requirements,
        detail=f"{diag['titulo']}: {diag['resumo']}",
        id=case.id, description=case.description,
        cycles=data.get("cycles"),
        duration_s=round(time.monotonic() - started, 2),
        log=str(log) if log and Path(log).exists() else None,
        diagnostico=diag,
    )


def _run_case(manifest: CpuManifest, case: Case, workdir: Path,
              rv32m: bool) -> CaseResult:
    """Monta, simula e confere um caso. Nunca levanta: devolve o veredito."""
    from .builder import (QUIET_IEEE_AT_ZERO, BuildFailed, build_design,
                          design_declares_generic, run_simulation)

    started = time.monotonic()
    allow_m = case.stage == "rv32m"
    try:
        words, _ = assemble_with_symbols(case.asm, base_address=0, allow_m=allow_m)
    except AssemblyError as e:
        return _failed(case, started, feedback.diagnosticar(
            nome=case.name, relatorio=None, tipo_forcado="interno",
            mensagem_forcada=f"o programa do caso nao montou: {e}"))

    halt_pcs = find_halt_addresses(words)
    if not halt_pcs:
        return _failed(case, started, feedback.diagnosticar(
            nome=case.name, relatorio=None, tipo_forcado="interno",
            mensagem_forcada="programa sem auto-laco de parada (ADR-003)"))

    if manifest.program.size_words and len(words) > manifest.program.size_words:
        return _failed(case, started, feedback.diagnosticar(
            nome=case.name, relatorio=None, tipo_forcado="rom_pequena",
            mensagem_forcada=(
                f"o programa tem {len(words)} palavras e nao cabe em "
                f"[program].size_words = {manifest.program.size_words}")))

    run_dir = workdir / f"case_{case.stage}_{case.name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    image = write_ram_image(words, run_dir / f"{case.name}.ram",
                            header=f"conformidade: {case.name}")
    report = run_dir / "report.json"
    log = run_dir / "sim.log"
    for stale in (report, log):
        stale.unlink(missing_ok=True)

    spec: dict = {
        "manifest": str(manifest.path),
        "name": case.name,
        "requirements": case.requirements,
        "max_cycles": case.max_cycles,
        "halt_pcs": halt_pcs,
        "expect_regs": {str(k): v for k, v in case.expect_regs.items()},
        "expect_ram": {hex(k): v for k, v in case.expect_ram.items()},
        "report_out": str(report),
    }
    pair_addrs: list[int] = []
    if case.expect_ram:
        # despejo de todos os slots: o diagnostico precisa tambem dos que
        # bateram para reconhecer uma instrucao executando no lugar de outra
        first, last = min(case.expect_ram), max(case.expect_ram)
        spec["dump_ram"] = {"start": first, "count": (last - first) // 4 + 1}
        if case.pairs:
            pair_addrs = sorted(case.expect_ram)
    spec_path = run_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    params: dict[str, object] = {
        manifest.program.generic: str(image),
    }
    if manifest.program.size_generic:
        params[manifest.program.size_generic] = manifest.program.size_words
    gname = manifest.design.rv32m_generic
    if gname and design_declares_generic(manifest, gname):
        params[gname] = "true" if rv32m else "false"

    try:
        built = build_design(manifest, log_file=workdir / "build.log")
    except BuildFailed as e:
        return _failed(case, started, feedback.diagnosticar(
            nome=case.name, relatorio=None, erros_compilacao=e.errors,
            mensagem_forcada=str(e)), log=e.log_file)

    excecao: BaseException | None = None
    try:
        run_simulation(built, test_module="rvverify.tb_generic",
                       parameters=params,
                       extra_env={"RVVERIFY_SPEC": str(spec_path)},
                       log_file=log, plusargs=[QUIET_IEEE_AT_ZERO])
    except KeyboardInterrupt:
        raise
    except BaseException as e:                       # noqa: BLE001
        # SimulationFailed e o resultado esperado de um caso reprovado;
        # qualquer outra coisa tambem vira reprovacao, nunca aprovacao.
        excecao = e

    data = _read_json(report)
    if excecao is None and data is not None and data.get("resultado") == "passou":
        return CaseResult(
            case.name, case.stage, True, case.requirements,
            id=case.id, description=case.description,
            cycles=data.get("cycles"),
            instructions=data.get("instructions"),
            cpi=data.get("cpi"),
            m_instructions=data.get("m_dispatches"),
            stalls=data.get("stalls"),
            flushes=data.get("flushes"),
            duration_s=round(time.monotonic() - started, 2),
            log=str(log) if log.exists() else None,
        )

    if excecao is None:
        # o cocotb aprovou mas o relatorio nao confirma: reprovar e dizer
        excecao = RuntimeError("a simulacao terminou sem relatorio de aprovacao")
    diag = feedback.diagnosticar(
        nome=case.name, relatorio=data, excecao=excecao,
        log_texto=_read_text(log), rotulos=case.labels,
        pares=case.pairs, enderecos_pares=pair_addrs,
    )
    return _failed(case, started, diag, log=log, data=data)


def _emit(on_event: EventSink | None, event: dict) -> None:
    if on_event is not None:
        on_event(event)


def _compile(manifest: CpuManifest, workdir: Path,
             on_event: EventSink | None) -> dict:
    """Compila uma vez antes do primeiro caso, para reportar o passo a parte.

    Uma falha aqui nao interrompe nada: cada caso tenta de novo, falha com o
    mesmo diagnostico e a CPU sai REPROVADA -- que e a verdade, nenhum
    programa roda numa CPU que nao compila.
    """
    from .builder import BuildFailed, build_design

    log = workdir / "build.log"
    _emit(on_event, {"tipo": "compilacao", "design": manifest.design.name,
                     "estado": "inicio"})
    started = time.monotonic()
    try:
        build_design(manifest, log_file=log)
        info: dict = {"ok": True, "erros": []}
    except BuildFailed as e:
        info = {"ok": False, "erros": e.errors, "mensagem": str(e)}
    info["segundos"] = round(time.monotonic() - started, 2)
    info["log"] = str(log) if log.exists() else None
    _emit(on_event, {"tipo": "compilacao", "design": manifest.design.name,
                     "estado": "ok" if info["ok"] else "erro", **info})
    return info


def plan_for(manifest: CpuManifest, stages: tuple[str, ...],
             only: set[str] | None) -> list[Case]:
    """Casos que uma execucao vai tentar, na ordem."""
    return [c for c in build_cases(manifest.memory.ram_base)
            if c.stage in stages and (only is None or c.id in only)]


def run_conformance(manifest_path: str | Path, workdir: Path,
                    *, stages: tuple[str, ...] = STAGES,
                    stop_on_base_failure: bool = True,
                    only: set[str] | None = None,
                    on_event: EventSink | None = None) -> dict:
    """Roda a suite contra um `cpu.toml` e devolve o relatorio.

    `stop_on_base_failure` implementa FR-RV-11: se o RV32I reprovar, a etapa da
    extensao nem roda, porque um defeito na base apareceria como se fosse da
    extensao.

    `only` restringe a execucao a um conjunto de ids de caso
    (`resolve_selection`); `on_event` recebe os eventos de FR-RV-29.
    """
    manifest = load_manifest(manifest_path)
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    all_cases = build_cases(manifest.memory.ram_base)
    selected = plan_for(manifest, stages, only)
    complete = ((only is None or {c.id for c in all_cases} <= only)
                and set(STAGES) <= set(stages))

    results: list[CaseResult] = []
    skipped: list[str] = []
    skipped_ids: list[str] = []
    compilation: dict = {"ok": None, "segundos": None, "erros": [], "log": None}

    for stage in stages:
        stage_cases = [c for c in selected if c.stage == stage]
        if not stage_cases:
            continue

        reason = None
        if stage == "rv32m" and not manifest.design.rv32m_generic:
            reason = ("etapa RV32M PULADA: o manifesto nao declara "
                      "[design].rv32m_generic, entao o validador nao sabe qual "
                      "generic liga a extensao. Nao e aprovacao.")
        elif (stage == "rv32m" and stop_on_base_failure
              and any(not r.passed for r in results if r.stage == "rv32i")):
            reason = ("etapa RV32M PULADA: a baseline RV32I reprovou. Corrija a "
                      "base primeiro -- um defeito nela apareceria como se "
                      "fosse da extensao (FR-RV-11).")
        if reason:
            skipped.append(reason)
            ids = [c.id for c in stage_cases]
            skipped_ids += ids
            _emit(on_event, {"tipo": "etapa_pulada",
                             "design": manifest.design.name,
                             "etapa": stage, "motivo": reason, "itens": ids})
            continue

        for case in stage_cases:
            if compilation["ok"] is None:
                compilation = _compile(manifest, workdir, on_event)
            _emit(on_event, {"tipo": "item", "design": manifest.design.name,
                             "id": case.id, "estado": "rodando"})
            result = _run_case(manifest, case, workdir, rv32m=(stage == "rv32m"))
            results.append(result)
            _emit(on_event, {"tipo": "item", "design": manifest.design.name,
                             "id": case.id,
                             "estado": "passou" if result.passed else "falhou",
                             "duracao_s": result.duration_s,
                             "resultado": vars(result)})

    # Agregacao por REQUISITO -- e o que transforma "3 casos falharam" em
    # "FR-RV-14 nao atendido". Um requisito so conta como atendido quando TODOS
    # os casos que o exercitam passam; um unico caso reprovado derruba o
    # requisito inteiro, porque cobertura parcial de um requisito nao e
    # atendimento dele.
    por_requisito: dict[str, dict] = {}
    for r in results:
        for req in r.requirements:
            e = por_requisito.setdefault(
                req, {"total": 0, "passou": 0, "casos_falhos": [],
                      "titulo": feedback.TITULOS_REQUISITO.get(req, "")})
            e["total"] += 1
            if r.passed:
                e["passou"] += 1
            else:
                e["casos_falhos"].append(r.name)
    for e in por_requisito.values():
        e["atendido"] = not e["casos_falhos"]

    por_etapa = {}
    for stage in stages:
        rs = [r for r in results if r.stage == stage]
        if rs:
            por_etapa[stage] = {
                "total": len(rs),
                "passou": sum(1 for r in rs if r.passed),
                "falhou": sum(1 for r in rs if not r.passed),
            }

    verdict = veredito(results, skipped, complete=complete)
    return {
        "design": manifest.design.name,
        "manifest": str(manifest.path),
        "veredito": verdict,
        "aprovado": verdict == "aprovado",
        "codigo_saida": exit_code_for(verdict),
        "escopo": {
            "completo": complete,
            "etapas": list(stages),
            "casos_selecionados": len(selected),
            "casos_na_suite": len(all_cases),
            "casos_pulados": skipped_ids,
        },
        "compilacao": compilation,
        "por_etapa": por_etapa,
        "por_requisito": dict(sorted(por_requisito.items())),
        "pulado": skipped,
        "observabilidade": manifest.observability(),
        "casos": [vars(r) for r in results],
    }
