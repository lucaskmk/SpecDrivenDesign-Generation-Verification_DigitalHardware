#!/usr/bin/env python3
"""Suite de conformidade: o que uma CPU precisa passar para valer como RV32I(M).

REQ: FR-RV-03 (ISA estritamente RISC-V), FR-RV-04, FR-RV-11 (baseline antes da
extensao), FR-RV-13 (as oito instrucoes M), FR-RV-14 (casos especiais),
FR-RV-16 (RV32I e RV32IM da mesma base), FR-RV-21, FR-RV-22, FR-RV-23
(modelo de referencia), NFR-RV-02 (nada declarado sem medir).

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

Sempre do modelo de referencia em Python (`reference_model.py`), nunca de
constante escrita a mao. Se o modelo e o hardware discordarem, o relatorio
mostra os dois valores lado a lado.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .builder import build_design, design_declares_generic, run_simulation
from .manifest import CpuManifest, load_manifest

REPO_ROOT = Path(__file__).resolve().parent.parent
_TOOLS = REPO_ROOT / "examples" / "RISCV32I" / "tools"
_REFDIR = REPO_ROOT / "examples" / "RISCV32I" / "test"
for _p in (_TOOLS, _REFDIR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import reference_model as ref            # noqa: E402
from rv_assembler import (               # noqa: E402
    AssemblyError,
    assemble_with_symbols,
    find_halt_addresses,
    write_ram_image,
)

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


# --------------------------------------------------------------------------
# Construtores de programa
# --------------------------------------------------------------------------

def _slots(base: int, values: list[int]) -> dict[int, int]:
    return {base + 4 * i: v & MASK32 for i, v in enumerate(values)}


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


def build_cases(base: int) -> list[Case]:
    """Todos os casos de conformidade, ja com o esperado do modelo."""
    cases: list[Case] = []

    # ---------------- etapa 1: RV32I ----------------
    for op in I_BINOPS:
        cases.append(_binop_case(op, _pairs(), base, "rv32i",
                                 ref.apply_i, ["FR-RV-04", "FR-RV-22"]))

    cases.append(Case(
        name="x0_imutavel",
        stage="rv32i",
        requirements=["FR-RV-04"],
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
        max_cycles=500,
    ))

    cases.append(Case(
        name="load_store_larguras",
        stage="rv32i",
        requirements=["FR-RV-04", "FR-RV-05"],
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
        max_cycles=800,
    ))

    cases.append(Case(
        name="branches",
        stage="rv32i",
        requirements=["FR-RV-04", "FR-RV-22"],
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
        max_cycles=800,
    ))

    cases.append(Case(
        name="jal_jalr_lui_auipc",
        stage="rv32i",
        requirements=["FR-RV-04"],
        asm=f"""
# JAL guarda o retorno, JALR volta; LUI e AUIPC formam constantes
    li   x18, {base}
    li   x20, 0
    jal  x1, sub_rotina
    addi x20, x20, 1            # executa DEPOIS do ret
    sw   x20, 0(x18)
    lui  x21, 0xABCDE
    sw   x21, 4(x18)
    j    fim
sub_rotina:
    addi x20, x20, 10
    jalr x0, 0(x1)
fim:
{HALT}""",
        expect_ram=_slots(base, [11, 0xABCDE000]),
        max_cycles=800,
    ))

    soma = sum(range(1, 11))
    cases.append(Case(
        name="laco_com_dependencia",
        stage="rv32i",
        requirements=["FR-RV-22"],
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
        max_cycles=800,
    ))

    lo = 0x80000000
    cases.append(Case(
        name="overflow_da_divisao",
        stage="rv32m",
        requirements=["FR-RV-14"],
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
        max_cycles=5000,
    ))

    return cases


# --------------------------------------------------------------------------
# Execucao
# --------------------------------------------------------------------------

def _run_case(manifest: CpuManifest, case: Case, workdir: Path,
              rv32m: bool) -> CaseResult:
    """Monta, simula e confere um caso. Nunca levanta: devolve o veredito."""
    allow_m = case.stage == "rv32m"
    try:
        words, _ = assemble_with_symbols(case.asm, base_address=0, allow_m=allow_m)
    except AssemblyError as e:
        return CaseResult(case.name, case.stage, False, case.requirements,
                          detail=f"o programa do caso nao montou: {e}")

    halt_pcs = find_halt_addresses(words)
    if not halt_pcs:
        return CaseResult(case.name, case.stage, False, case.requirements,
                          detail="programa sem auto-laco de parada (ADR-003)")

    if len(words) > manifest.program.size_words:
        return CaseResult(
            case.name, case.stage, False, case.requirements,
            detail=(f"o programa tem {len(words)} palavras e nao cabe em "
                    f"[program].size_words = {manifest.program.size_words}"))

    run_dir = workdir / f"case_{case.stage}_{case.name}"
    run_dir.mkdir(parents=True, exist_ok=True)
    image = write_ram_image(words, run_dir / f"{case.name}.ram",
                            header=f"conformidade: {case.name}")
    report = run_dir / "report.json"

    spec = {
        "manifest": str(manifest.path),
        "name": case.name,
        "requirements": case.requirements,
        "max_cycles": case.max_cycles,
        "halt_pcs": halt_pcs,
        "expect_regs": {str(k): v for k, v in case.expect_regs.items()},
        "expect_ram": {hex(k): v for k, v in case.expect_ram.items()},
        "report_out": str(report),
    }
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
        built = build_design(manifest)
        run_simulation(built, test_module="rvverify.tb_generic",
                       parameters=params,
                       extra_env={"RVVERIFY_SPEC": str(spec_path)})
    except BaseException as e:                       # noqa: BLE001
        # O runner do cocotb sai com sys.exit(codigo) quando a simulacao
        # reprova -- SystemExit e um resultado esperado aqui, nao um crash.
        detail = _explain(report, e)
        return CaseResult(case.name, case.stage, False, case.requirements,
                          detail=detail)

    data = json.loads(report.read_text(encoding="utf-8")) if report.exists() else {}
    return CaseResult(
        case.name, case.stage, True, case.requirements,
        cycles=data.get("cycles"),
        instructions=data.get("instructions"),
        cpi=data.get("cpi"),
        m_instructions=data.get("m_dispatches"),
    )


def _explain(report: Path, exc: BaseException) -> str:
    """Mensagem util a partir do que sobrou da execucao que falhou."""
    if isinstance(exc, SystemExit):
        return "a simulacao reprovou (exit code != 0); ver o log do GHDL acima"
    return f"{type(exc).__name__}: {exc}"


def run_conformance(manifest_path: str | Path, workdir: Path,
                    *, stages: tuple[str, ...] = ("rv32i", "rv32m"),
                    stop_on_base_failure: bool = True) -> dict:
    """Roda a suite inteira contra um `cpu.toml` e devolve o relatorio.

    `stop_on_base_failure` implementa FR-RV-11: se o RV32I reprovar, a etapa da
    extensao nem roda, porque um defeito na base apareceria como se fosse da
    extensao.
    """
    manifest = load_manifest(manifest_path)
    base = manifest.memory.ram_base
    all_cases = build_cases(base)
    results: list[CaseResult] = []
    skipped: list[str] = []

    for stage in stages:
        stage_cases = [c for c in all_cases if c.stage == stage]

        if stage == "rv32m" and not manifest.design.rv32m_generic:
            skipped.append(
                "etapa RV32M PULADA: o manifesto nao declara "
                "[design].rv32m_generic, entao o validador nao sabe qual "
                "generic liga a extensao. Nao e aprovacao."
            )
            continue

        if (stage == "rv32m" and stop_on_base_failure
                and any(not r.passed for r in results if r.stage == "rv32i")):
            skipped.append(
                "etapa RV32M PULADA: a baseline RV32I reprovou. Corrija a base "
                "primeiro -- um defeito nela apareceria como se fosse da "
                "extensao (FR-RV-11)."
            )
            continue

        for case in stage_cases:
            results.append(_run_case(manifest, case, workdir,
                                     rv32m=(stage == "rv32m")))

    por_etapa = {}
    for stage in stages:
        rs = [r for r in results if r.stage == stage]
        if rs:
            por_etapa[stage] = {
                "total": len(rs),
                "passou": sum(1 for r in rs if r.passed),
                "falhou": sum(1 for r in rs if not r.passed),
            }

    return {
        "design": manifest.design.name,
        "manifest": str(manifest.path),
        "aprovado": bool(results) and all(r.passed for r in results) and not skipped,
        "por_etapa": por_etapa,
        "pulado": skipped,
        "casos": [vars(r) for r in results],
    }
