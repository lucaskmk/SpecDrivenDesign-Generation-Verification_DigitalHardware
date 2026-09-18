#!/usr/bin/env python3
"""Smoke test da CPU RISC-V monociclo, executado de verdade no GHDL.

REQ: FR-RV-03, FR-RV-04, FR-RV-05, FR-RV-06, FR-RV-09, FR-RV-12, FR-RV-13,
     FR-RV-14, FR-RV-15, FR-RV-16, FR-RV-21, FR-RV-22, FR-RV-23,
     NFR-RV-01, NFR-RV-02

Cada teste monta um programa com o montador de
`examples/RISCV32I/tools/rv_assembler.py`, grava a imagem `.ram`, elabora o
design com `-gROM_INIT_FILE=...` e roda `ghdl -r` através do
`cocotb_tools.runner`. Nada aqui é inferido do RTL: se o GHDL falhar ou o
testbench reprovar, `runner.test` levanta exceção e o pytest falha.

Todo valor esperado vem do modelo de referência em
`examples/RISCV32I/test/reference_model.py` ou de um modelo Python da semântica
de memória escrito aqui (little-endian, larguras de 8/16/32 bits). Nenhum
valor esperado foi copiado de uma execução (FR-RV-23).

Este arquivo é autossuficiente: não usa `rv_build.py`, `rv_harness.py` nem o
pacote `rvverify`. A CPU monociclo existe para provar que o mecanismo de
conformidade não está preso ao design pipeline, e um smoke test que dependesse
do outro design não provaria isso.

Como rodar (WSL):
    RV_BUILD_ROOT=$HOME/rvb_mono ~/venv-cocotb/bin/python -m pytest \\
        examples/rv32i_monociclo/test/test_monociclo.py -o addopts= -q
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest
from cocotb_tools.runner import VHDL, get_runner

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent                       # cpus/rv32i_monociclo
CPUS = EXAMPLE_ROOT.parent                       # cpus/
PIPELINE_SRC = CPUS / "rv32i_pipeline" / "src"
PIPELINE_TEST = CPUS / "rv32i_pipeline" / "test"
PIPELINE_TOOLS = CPUS / "rv32i_pipeline" / "tools"
MONO_SRC = EXAMPLE_ROOT / "src"

sys.path.insert(0, str(PIPELINE_TOOLS))
sys.path.insert(0, str(PIPELINE_TEST))

import reference_model as ref  # noqa: E402
from rv_assembler import (  # noqa: E402
    assemble_with_symbols,
    find_halt_addresses,
    write_ram_image,
)

MASK32 = 0xFFFFFFFF

# Mapa de memória: idêntico ao da CPU pipeline, porque as memórias são as
# mesmas (memory_package.vhd).
RAM_BASE = 0x00FC8100
RAM_BYTES = 512
ROM_SIZE_WORDS = 1024

TOP = "cpu_monocycle"

# Ordem de análise -- a mesma lista de `cpu.toml`, [design].sources
VHDL_SOURCES = [
    PIPELINE_SRC / "cpu_package.vhd",
    PIPELINE_SRC / "memory_package.vhd",
    PIPELINE_SRC / "mul_div_unit.vhd",
    PIPELINE_SRC / "data_ram.vhd",
    PIPELINE_SRC / "data_rom.vhd",
    PIPELINE_SRC / "data_memory.vhd",
    PIPELINE_SRC / "instruction_memory.vhd",
    MONO_SRC / "mono_alu.vhd",
    MONO_SRC / "mono_control.vhd",
    MONO_SRC / "mono_regfile.vhd",
    MONO_SRC / "cpu_monocycle.vhd",
]

_BUILD_ROOT = Path(os.environ.get("RV_BUILD_ROOT", Path.home() / "rv32_mono_build"))
_build_cache: dict[str, tuple[Path, object]] = {}


# ==========================================================================
# Infraestrutura de execução
# ==========================================================================

def _sources_stamp() -> str:
    h = hashlib.sha256()
    for p in VHDL_SOURCES:
        st = p.stat()
        h.update(f"{p.name}:{st.st_size}:{st.st_mtime_ns}\n".encode())
    return h.hexdigest()[:16]


def _ensure_build() -> tuple[Path, object]:
    """Compila o design uma vez por sessão e devolve (build_dir, runner).

    O GHDL aplica generics na ELABORAÇÃO (`ghdl -r` no backend mcode), então
    compilar uma vez e variar apenas os generics em cada execução evita
    recompilar os 11 fontes a cada caso de teste.
    """
    stamp = _sources_stamp()
    cached = _build_cache.get(stamp)
    if cached is not None and cached[0].exists():
        return cached

    missing = [str(p) for p in VHDL_SOURCES if not p.exists()]
    if missing:
        raise RuntimeError("fontes VHDL ausentes: " + ", ".join(missing))

    build_dir = _BUILD_ROOT / f"mono_{stamp}"
    build_dir.mkdir(parents=True, exist_ok=True)

    runner = get_runner("ghdl")
    runner.build(
        sources=[VHDL(p) for p in VHDL_SOURCES],
        hdl_toplevel=TOP,
        build_args=["--std=08"],
        build_dir=build_dir,
        always=True,
    )
    _build_cache[stamp] = (build_dir, runner)
    return build_dir, runner


def run_program(tmp_path: Path, name: str, asm: str, *,
                rv32m: bool = False,
                max_cycles: int = 20000,
                requirements: list[str] | None = None,
                dump_ram_words: int = RAM_BYTES // 4) -> dict:
    """Monta `asm`, executa no GHDL e devolve o estado observado.

    O retorno tem as chaves `metrics`, `registers`, `ram`, `x0_storage` e
    ainda `symbols` (tabela de símbolos do montador, útil para valores
    esperados que dependem de endereço, como o de JAL).
    """
    words, symbols = assemble_with_symbols(asm, base_address=0, allow_m=rv32m)
    if len(words) > ROM_SIZE_WORDS:
        raise ValueError(f"programa {name!r} tem {len(words)} palavras, "
                         f"maior que ROM_SIZE_WORDS={ROM_SIZE_WORDS}")

    halt_pcs = find_halt_addresses(words)
    if not halt_pcs:
        raise ValueError(f"programa {name!r} não termina em auto-laço "
                         f"(`halt: j halt`), exigido pela convenção de parada")

    run_dir = tmp_path / f"run_{name}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    run_dir.mkdir(parents=True, exist_ok=True)

    image = write_ram_image(
        words, run_dir / f"{name}.ram",
        header=f"programa: {name}\n"
               f"requisitos: {', '.join(requirements or [])}\n"
               f"palavras: {len(words)}   parada em: "
               f"{', '.join(hex(p) for p in halt_pcs)}\n"
               f"gerado por examples/RISCV32I/tools/rv_assembler.py",
    )

    state_out = run_dir / "state.json"
    spec = {
        "name": name,
        "image": str(image),
        "halt_pcs": halt_pcs,
        "max_cycles": max_cycles,
        "drain": 2,
        "reset_cycles": 3,
        "ram_base": RAM_BASE,
        "ram_bytes": RAM_BYTES,
        "dump_ram_words": dump_ram_words,
        "requirements": requirements or [],
        "state_out": str(state_out),
    }
    spec_path = run_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    build_dir, runner = _ensure_build()

    env = dict(os.environ)
    env["RV_MONO_SPEC"] = str(spec_path)
    env["PYTHONPATH"] = os.pathsep.join([str(HERE), env.get("PYTHONPATH", "")])

    runner.test(
        hdl_toplevel=TOP,
        hdl_toplevel_lang="vhdl",
        test_module="tb_mono",
        test_args=["--std=08"],
        build_dir=build_dir,
        parameters={
            "ROM_INIT_FILE": str(image),
            "ROM_SIZE_WORDS": ROM_SIZE_WORDS,
            "RV32M_ENABLE": "true" if rv32m else "false",
        },
        extra_env=env,
        waves=False,
    )

    state = json.loads(state_out.read_text(encoding="utf-8"))
    state["symbols"] = symbols
    state["words"] = words

    # Invariante da microarquitetura: um monociclo retira exatamente uma
    # instrução por ciclo. Verificado em TODA execução, e não assumido.
    m = state["metrics"]
    assert m["cycles"] == m["instructions"], (
        f"[{name}] monociclo deveria ter 1 instrução por ciclo, "
        f"tem {m['instructions']} instruções em {m['cycles']} ciclos"
    )
    assert m["cpi"] == 1.0, f"[{name}] CPI deveria ser exatamente 1, é {m['cpi']}"
    # x0 nunca é escrito, nem no armazenamento (FR-RV-04)
    assert state["x0_storage"] == 0, (
        f"[{name}] a posição 0 do banco de registradores foi escrita: "
        f"{state['x0_storage']:#010x} (FR-RV-04)"
    )
    return state


# ==========================================================================
# Construção de programas
# ==========================================================================

def _imm(value: int) -> str:
    """Formata um inteiro como operando do montador."""
    return hex(value) if value >= 0 else str(value)


class Prog:
    """Montador de programas de teste com slots de resultado na RAM.

    x1 fica reservado como ponteiro para a base da RAM de dados; os testes
    usam x5 em diante.
    """

    def __init__(self) -> None:
        self._lines: list[str] = [
            "    # x1 = base da RAM de dados (0x00FC8100)",
            "    li x1, 0x00FC8100",
        ]
        self.slots = 0

    def add(self, *lines: str) -> None:
        self._lines.extend("    " + ln for ln in lines)

    def label(self, name: str) -> None:
        self._lines.append(f"{name}:")

    def li(self, reg: str, value: int) -> None:
        self.add(f"li {reg}, {_imm(value)}")

    def store(self, reg: str) -> int:
        """Publica `reg` no próximo slot livre da RAM e devolve o índice."""
        slot = self.slots
        self.slots += 1
        if 4 * slot >= RAM_BYTES:
            raise ValueError("slots de resultado esgotados")
        self.add(f"sw {reg}, {4 * slot}(x1)")
        return slot

    def text(self) -> str:
        return "\n".join(self._lines + ["halt:", "    j halt", ""])


def ram_slot(state: dict, slot: int) -> int:
    return state["ram"][hex(RAM_BASE + 4 * slot)]


def fmt(value: int) -> str:
    v = value & MASK32
    return f"{v:#010x} ({ref.to_signed32(v)})"


def check(failures: list[str], what: str, got: int, expected: int) -> None:
    if (got & MASK32) != (expected & MASK32):
        failures.append(f"  {what}: esperado {fmt(expected)}, obtido {fmt(got)}")


# ==========================================================================
# 1. Aritmética R-type
# ==========================================================================

R_CASES = [
    ("add",  0x12345678, 0xDEADBEEF),
    ("add",  0x7FFFFFFF, 0x00000001),   # estouro dá a volta, sem trap
    ("sub",  0x00000000, 0x00000001),
    ("sub",  0x80000000, 0x00000001),
    ("and",  0xF0F0F0F0, 0x0FF00FF0),
    ("or",   0xF0F0F0F0, 0x0FF00FF0),
    ("xor",  0xF0F0F0F0, 0x0FF00FF0),
    ("sll",  0x00000001, 0x0000001F),
    ("sll",  0xDEADBEEF, 0x00000024),   # só os 5 bits baixos contam -> shamt 4
    ("srl",  0x80000000, 0x0000001F),
    ("srl",  0xDEADBEEF, 0x00000024),
    ("sra",  0x80000000, 0x0000001F),
    ("sra",  0x7FFFFFFF, 0x0000001F),
    ("slt",  0xFFFFFFFF, 0x00000001),   # -1 < 1
    ("slt",  0x00000001, 0xFFFFFFFF),
    ("sltu", 0xFFFFFFFF, 0x00000001),   # 4294967295 < 1 é falso
    ("sltu", 0x00000001, 0xFFFFFFFF),
    ("sub",  0x12345678, 0x12345678),
]


def test_r_type(tmp_path):
    """As 10 operações R-type, com valores de borda (FR-RV-22, FR-RV-23)."""
    p = Prog()
    for op, a, b in R_CASES:
        p.li("x10", a)
        p.li("x11", b)
        p.add(f"{op} x12, x10, x11")
        p.store("x12")

    state = run_program(tmp_path, "r_type", p.text(),
                        requirements=["FR-RV-03", "FR-RV-22", "FR-RV-23"])

    failures: list[str] = []
    for slot, (op, a, b) in enumerate(R_CASES):
        check(failures, f"{op}({fmt(a)}, {fmt(b)})",
              ram_slot(state, slot), ref.apply_i(op, a, b))
    assert not failures, "R-type divergiu do modelo de referência:\n" + "\n".join(failures)


# ==========================================================================
# 2. Aritmética I-type
# ==========================================================================

# (mnemônico, operação equivalente no modelo, rs1, imediato)
I_CASES = [
    ("addi",  "add",  0x12345678,    -1),
    ("addi",  "add",  0xFFFFFFFF,     1),
    ("addi",  "add",  0x00000000, -2048),   # menor imediato de 12 bits
    ("addi",  "add",  0x00000000,  2047),   # maior imediato de 12 bits
    ("slti",  "slt",  0xFFFFFFFF,     0),   # -1 < 0
    ("slti",  "slt",  0x00000005,    -6),
    ("sltiu", "sltu", 0xFFFFFFFF,    -1),   # 0xFFFFFFFF < 0xFFFFFFFF é falso
    ("sltiu", "sltu", 0x00000000,    -1),   # 0 < 0xFFFFFFFF
    ("xori",  "xor",  0x12345678,    -1),   # complemento de 1
    ("ori",   "or",   0x12340000, 0x555),
    ("andi",  "and",  0x12345678, 0x7F0),
    ("andi",  "and",  0x12345678,    -1),   # imediato negativo estende sinal
    ("slli",  "sll",  0x00000001,    31),
    ("slli",  "sll",  0xDEADBEEF,     4),
    ("srli",  "srl",  0x80000000,    31),
    ("srai",  "sra",  0x80000000,    31),
    ("srai",  "sra",  0x80000000,     1),
    ("srai",  "sra",  0x7FFFFFFF,     1),
]


def test_i_type(tmp_path):
    """As 9 operações I-type, incluindo os extremos do imediato de 12 bits."""
    p = Prog()
    for mnem, _ref_op, rs1, imm in I_CASES:
        p.li("x10", rs1)
        p.add(f"{mnem} x12, x10, {_imm(imm)}")
        p.store("x12")

    state = run_program(tmp_path, "i_type", p.text(),
                        requirements=["FR-RV-03", "FR-RV-22", "FR-RV-23"])

    failures: list[str] = []
    for slot, (mnem, ref_op, rs1, imm) in enumerate(I_CASES):
        expected = ref.apply_i(ref_op, rs1, imm & MASK32)
        check(failures, f"{mnem}({fmt(rs1)}, {imm})", ram_slot(state, slot), expected)
    assert not failures, "I-type divergiu do modelo de referência:\n" + "\n".join(failures)


# ==========================================================================
# 3. LUI e AUIPC
# ==========================================================================

def test_lui_auipc(tmp_path):
    """LUI monta a metade alta; AUIPC soma o imediato ao PC da própria instrução."""
    p = Prog()
    p.add("lui x5, 0xABCDE")
    p.store("x5")                       # slot 0
    p.label("auipc_a")
    p.add("auipc x6, 0x1")
    p.store("x6")                       # slot 1
    p.label("auipc_b")
    p.add("auipc x7, 0x0")
    p.store("x7")                       # slot 2
    p.add("lui x8, 0x0")
    p.store("x8")                       # slot 3

    state = run_program(tmp_path, "lui_auipc", p.text(),
                        requirements=["FR-RV-03", "FR-RV-22"])
    sym = state["symbols"]

    failures: list[str] = []
    check(failures, "lui 0xABCDE", ram_slot(state, 0), 0xABCDE000)
    check(failures, "auipc +0x1000", ram_slot(state, 1), sym["auipc_a"] + 0x1000)
    check(failures, "auipc +0", ram_slot(state, 2), sym["auipc_b"])
    check(failures, "lui 0", ram_slot(state, 3), 0)
    assert not failures, "LUI/AUIPC divergiu:\n" + "\n".join(failures)


# ==========================================================================
# 4. Loads e stores nas três larguras
# ==========================================================================

def _mem_byte(word: int, offset: int) -> int:
    """Byte `offset` (0..3) de uma palavra little-endian."""
    return (word >> (8 * offset)) & 0xFF


def _mem_half(word: int, offset: int) -> int:
    """Meia-palavra alinhada em `offset` (0 ou 2), little-endian."""
    return (word >> (8 * offset)) & 0xFFFF


def _sext(value: int, bits: int) -> int:
    sign = 1 << (bits - 1)
    return ((value & (sign - 1)) - (value & sign)) & MASK32


def test_load_store_larguras(tmp_path):
    """LB/LBU/LH/LHU/LW e SB/SH/SW, com o modelo little-endian conferido em Python.

    REQ: FR-RV-03, FR-RV-06, FR-RV-22
    """
    pattern = 0x89ABCDEF
    # área de trabalho fora dos slots de resultado
    work_sw = 0x100      # offset em bytes a partir de x1: palavra escrita por sw
    work_sb = 0x110      # palavra montada byte a byte
    work_sh = 0x114      # palavra montada meia-palavra a meia-palavra
    bytes_in = [0x11, 0x22, 0x33, 0x44]
    halves_in = [0xBEEF, 0xDEAD]

    p = Prog()
    p.li("x10", pattern)
    p.add(f"sw x10, {work_sw}(x1)")

    loads = [
        ("lw",  0), ("lb",  0), ("lbu", 0), ("lb",  1), ("lbu", 1),
        ("lb",  2), ("lbu", 2), ("lb",  3), ("lbu", 3),
        ("lh",  0), ("lhu", 0), ("lh",  2), ("lhu", 2),
    ]
    for mnem, off in loads:
        p.add(f"{mnem} x12, {work_sw + off}(x1)")
        p.store("x12")

    # SB: monta uma palavra byte a byte sobre uma posição zerada
    p.add(f"sw x0, {work_sb}(x1)")
    for i, b in enumerate(bytes_in):
        p.li("x13", b)
        p.add(f"sb x13, {work_sb + i}(x1)")
    p.add(f"lw x14, {work_sb}(x1)")
    slot_sb = p.store("x14")

    # SH: idem, meia-palavra a meia-palavra. `li` carrega 32 bits, mas `sh`
    # só grava os 16 baixos -- é exatamente isso que se quer verificar.
    p.add(f"sw x0, {work_sh}(x1)")
    for i, h in enumerate(halves_in):
        p.li("x15", 0xFFFF0000 | h)
        p.add(f"sh x15, {work_sh + 2 * i}(x1)")
    p.add(f"lw x16, {work_sh}(x1)")
    slot_sh = p.store("x16")

    state = run_program(tmp_path, "load_store", p.text(),
                        requirements=["FR-RV-03", "FR-RV-06", "FR-RV-22"])

    failures: list[str] = []
    for slot, (mnem, off) in enumerate(loads):
        if mnem == "lw":
            expected = pattern
        elif mnem == "lb":
            expected = _sext(_mem_byte(pattern, off), 8)
        elif mnem == "lbu":
            expected = _mem_byte(pattern, off)
        elif mnem == "lh":
            expected = _sext(_mem_half(pattern, off), 16)
        else:
            expected = _mem_half(pattern, off)
        check(failures, f"{mnem} offset {off}", ram_slot(state, slot), expected)

    expected_sb = sum(b << (8 * i) for i, b in enumerate(bytes_in))
    check(failures, "palavra montada com 4x sb", ram_slot(state, slot_sb), expected_sb)

    expected_sh = sum(h << (16 * i) for i, h in enumerate(halves_in))
    check(failures, "palavra montada com 2x sh", ram_slot(state, slot_sh), expected_sh)

    # a palavra original tem de continuar intacta na RAM
    check(failures, "palavra escrita por sw",
          state["ram"][hex(RAM_BASE + work_sw)], pattern)

    assert not failures, "load/store divergiu:\n" + "\n".join(failures)


# ==========================================================================
# 5. Branches tomados e não tomados
# ==========================================================================

BRANCH_CASES = [
    # (mnemônico, rs1, rs2)  -- cada par aparece nas duas direções
    ("beq",  0x00000005, 0x00000005),
    ("beq",  0x00000005, 0x00000006),
    ("bne",  0x00000005, 0x00000006),
    ("bne",  0x00000005, 0x00000005),
    ("blt",  0xFFFFFFFF, 0x00000001),   # -1 < 1
    ("blt",  0x00000001, 0xFFFFFFFF),
    ("bge",  0x00000001, 0xFFFFFFFF),   # 1 >= -1
    ("bge",  0xFFFFFFFF, 0x00000001),
    ("bge",  0x00000005, 0x00000005),   # igualdade também toma
    ("bltu", 0x00000001, 0xFFFFFFFF),   # 1 < 4294967295
    ("bltu", 0xFFFFFFFF, 0x00000001),
    ("bgeu", 0xFFFFFFFF, 0x00000001),
    ("bgeu", 0x00000001, 0xFFFFFFFF),
    ("bgeu", 0x00000005, 0x00000005),
]


def _branch_taken(mnem: str, a: int, b: int) -> bool:
    sa, sb = ref.to_signed32(a), ref.to_signed32(b)
    ua, ub = ref.to_unsigned32(a), ref.to_unsigned32(b)
    return {
        "beq": ua == ub, "bne": ua != ub,
        "blt": sa < sb, "bge": sa >= sb,
        "bltu": ua < ub, "bgeu": ua >= ub,
    }[mnem]


def test_branches(tmp_path):
    """Os 6 branches, cada um tomado e não tomado (FR-RV-22)."""
    p = Prog()
    for i, (mnem, a, b) in enumerate(BRANCH_CASES):
        p.li("x10", a)
        p.li("x11", b)
        p.li("x12", 0)
        p.add(f"{mnem} x10, x11, taken_{i}")
        p.add(f"j done_{i}")
        p.label(f"taken_{i}")
        p.li("x12", 1)
        p.label(f"done_{i}")
        p.store("x12")

    state = run_program(tmp_path, "branches", p.text(),
                        requirements=["FR-RV-03", "FR-RV-22"])

    failures: list[str] = []
    for slot, (mnem, a, b) in enumerate(BRANCH_CASES):
        expected = 1 if _branch_taken(mnem, a, b) else 0
        check(failures, f"{mnem}({fmt(a)}, {fmt(b)}) tomado?",
              ram_slot(state, slot), expected)
    assert not failures, "branches divergiram:\n" + "\n".join(failures)


# ==========================================================================
# 6. JAL e JALR
# ==========================================================================

def test_jal_jalr(tmp_path):
    """JAL grava PC+4 e desvia; JALR desvia por registrador e zera o bit 0.

    REQ: FR-RV-03, FR-RV-22
    """
    p = Prog()
    p.li("x20", 0)
    p.add("jal x5, sub_a")               # x5 = endereço de after_jal
    p.label("after_jal")
    p.add("addi x20, x20, 1")            # só executa depois do retorno
    p.store("x5")                        # slot 0: endereço de retorno de JAL
    p.store("x6")                        # slot 1: PC capturado dentro da sub
    p.store("x20")                       # slot 2: prova que voltou e seguiu

    # JALR com destino calculado: pula por cima de uma instrução.
    # A instrução pulada é escrita como `addi` cru, e não como `li`, porque
    # `li` pode expandir para duas instruções e o salto deixaria de cair no
    # rótulo.
    p.add("auipc x7, 0x0")
    p.label("auipc_base")
    p.add("jalr x8, 12(x7)")             # alvo = (auipc_base - 4) + 12
    p.add("addi x20, x0, 173")           # PULADA
    p.label("jalr_target")
    p.store("x8")                        # slot 3: endereço de retorno de JALR
    p.store("x20")                       # slot 4: continua 1 se a pulada valeu

    p.add("j fim")
    p.label("sub_a")
    p.add("auipc x6, 0x0")               # x6 = endereço de sub_a
    p.add("jalr x0, 1(x5)")              # retorno; o bit 0 tem de ser zerado
    p.label("fim")
    p.add("nop")

    state = run_program(tmp_path, "jal_jalr", p.text(),
                        requirements=["FR-RV-03", "FR-RV-22"])
    sym = state["symbols"]

    failures: list[str] = []
    check(failures, "x5 = PC+4 do JAL", ram_slot(state, 0), sym["after_jal"])
    check(failures, "x6 = endereço de sub_a", ram_slot(state, 1), sym["sub_a"])
    check(failures, "x20 após o retorno", ram_slot(state, 2), 1)
    # `auipc x7,0` está uma instrução antes de auipc_base
    auipc_addr = sym["auipc_base"] - 4
    check(failures, "x8 = PC+4 do JALR", ram_slot(state, 3), sym["auipc_base"] + 4)
    check(failures, "instrução pulada pelo JALR não executou",
          ram_slot(state, 4), 1)
    assert not failures, "JAL/JALR divergiu:\n" + "\n".join(failures)

    # o alvo calculado tem de bater com o rótulo, senão o teste não prova nada
    assert auipc_addr + 12 == sym["jalr_target"], (
        f"o teste está mal montado: alvo do jalr {auipc_addr + 12:#x} != "
        f"jalr_target {sym['jalr_target']:#x}"
    )


# ==========================================================================
# 7. x0 permanentemente zero
# ==========================================================================

def test_x0_sempre_zero(tmp_path):
    """Nenhuma forma de escrita altera x0 (FR-RV-04)."""
    p = Prog()
    p.li("x10", 0x12345678)
    p.add(f"sw x10, {0x100}(x1)")
    p.add("addi x0, x0, 5")              # I-type
    p.add("add x0, x10, x10")            # R-type
    p.add("lui x0, 0xABCDE")             # U-type
    p.add("auipc x0, 0xABCDE")           # U-type
    p.add(f"lw x0, {0x100}(x1)")         # load
    p.add("jal x0, depois")              # link em x0
    p.label("depois")
    p.store("x0")                        # slot 0: tem de ser 0
    p.add("add x11, x0, x0")
    p.store("x11")                       # slot 1
    p.add("addi x12, x0, 7")
    p.store("x12")                       # slot 2: 0 + 7

    state = run_program(tmp_path, "x0_zero", p.text(),
                        requirements=["FR-RV-04"])

    failures: list[str] = []
    check(failures, "sw x0", ram_slot(state, 0), 0)
    check(failures, "x0 + x0", ram_slot(state, 1), 0)
    check(failures, "x0 + 7", ram_slot(state, 2), 7)
    check(failures, "leitura de x0", state["registers"][0], 0)
    check(failures, "armazenamento de x0", state["x0_storage"], 0)
    assert not failures, "x0 deixou de ser zero:\n" + "\n".join(failures)


# ==========================================================================
# 8. Laço com dependência entre instruções
# ==========================================================================

def test_laco_com_dependencia(tmp_path):
    """Somatório 1..N num laço, e depois soma de um vetor lido da RAM.

    Num pipeline isto exercitaria forwarding e stall de load-use; num
    monociclo tem de simplesmente funcionar, porque cada instrução vê o
    estado já comitado pela anterior. Esse contraste é o ponto do teste.

    REQ: FR-RV-03, FR-RV-06, FR-RV-22
    """
    n = 10
    vector = [3, 1, 4, 1, 5, 9, 2, 6]
    vec_off = 0x100

    p = Prog()
    # --- somatório 1..n, dependência registrador->registrador ---
    p.li("x5", 0)                        # soma
    p.li("x6", 1)                        # i
    p.li("x7", n + 1)                    # limite
    p.label("loop1")
    p.add("bge x6, x7, fim1")
    p.add("add x5, x5, x6")              # depende de si mesma
    p.add("addi x6, x6, 1")
    p.add("j loop1")
    p.label("fim1")
    p.store("x5")                        # slot 0

    # --- grava o vetor na RAM ---
    for i, v in enumerate(vector):
        p.li("x8", v)
        p.add(f"sw x8, {vec_off + 4 * i}(x1)")

    # --- soma o vetor com load-use imediato ---
    p.li("x9", 0)                        # acumulador
    p.li("x10", 0)                       # índice em bytes
    p.li("x11", 4 * len(vector))
    p.label("loop2")
    p.add("bge x10, x11, fim2")
    p.add("add x12, x1, x10")
    p.add(f"lw x13, {vec_off}(x12)")
    p.add("add x9, x9, x13")             # usa o resultado do load imediatamente
    p.add("addi x10, x10, 4")
    p.add("j loop2")
    p.label("fim2")
    p.store("x9")                        # slot 1

    # --- laço decrescente com dependência multiplicativa por somas ---
    p.li("x14", 0)
    p.li("x15", 5)
    p.label("loop3")
    p.add("beq x15, x0, fim3")
    p.add("add x14, x14, x15")
    p.add("addi x15, x15, -1")
    p.add("j loop3")
    p.label("fim3")
    p.store("x14")                       # slot 2

    state = run_program(tmp_path, "laco", p.text(),
                        requirements=["FR-RV-03", "FR-RV-06", "FR-RV-22"])

    failures: list[str] = []
    check(failures, f"somatório 1..{n}", ram_slot(state, 0), n * (n + 1) // 2)
    check(failures, "soma do vetor lido da RAM", ram_slot(state, 1), sum(vector))
    check(failures, "somatório decrescente 5..1", ram_slot(state, 2), 15)
    assert not failures, "laço com dependência divergiu:\n" + "\n".join(failures)


# ==========================================================================
# 9. Extensão RV32M
# ==========================================================================

M_OPS = ["mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"]

M_PAIRS = [
    (0x00000007, 0x00000003),
    (0xFFFFFFF9, 0x00000003),   # -7 op 3
    (0x00000007, 0xFFFFFFFD),   # 7 op -3
    (0x80000000, 0xFFFFFFFF),   # overflow de divisão: -2^31 / -1
    (0x12345678, 0x00000000),   # divisão por zero
    (0xFFFFFFFF, 0xFFFFFFFF),   # -1 op -1
    (0x7FFFFFFF, 0x7FFFFFFF),
    (0xDEADBEEF, 0x0000FFFF),
]


def test_rv32m(tmp_path):
    """As 8 instruções da extensão M, com RV32M_ENABLE=true.

    Inclui explicitamente os casos especiais da spec RISC-V: divisão por zero
    (DIV -> -1, DIVU -> 2^32-1, REM/REMU -> dividendo) e o overflow
    (-2^31)/(-1) -> -2^31, com REM correspondente 0. Nenhum trap.

    REQ: FR-RV-12, FR-RV-13, FR-RV-14, FR-RV-16, FR-RV-17
    """
    p = Prog()
    for a, b in M_PAIRS:
        p.li("x10", a)
        p.li("x11", b)
        for op in M_OPS:
            p.add(f"{op} x12, x10, x11")
            p.store("x12")

    state = run_program(tmp_path, "rv32m", p.text(), rv32m=True,
                        requirements=["FR-RV-12", "FR-RV-13", "FR-RV-14",
                                      "FR-RV-16", "FR-RV-17"])

    failures: list[str] = []
    slot = 0
    for a, b in M_PAIRS:
        for op in M_OPS:
            check(failures, f"{op}({fmt(a)}, {fmt(b)})",
                  ram_slot(state, slot), ref.apply_m(op, a, b))
            slot += 1
    assert not failures, "RV32M divergiu do modelo de referência:\n" + "\n".join(failures)

    # métrica real: uma dispatch por instrução M executada
    esperado = len(M_PAIRS) * len(M_OPS)
    assert state["metrics"]["m_dispatches"] == esperado, (
        f"m_dispatch contou {state['metrics']['m_dispatches']} instruções M, "
        f"esperado {esperado}"
    )


def test_rv32m_desligado_nao_conta_dispatch(tmp_path):
    """Com RV32M_ENABLE=false a métrica m_dispatch é constante zero.

    Serve de controle: prova que o contador de RV32M mede o design e não o
    testbench, e que a configuração RV32I é observável pelos mesmos sinais
    (FR-RV-16, FR-RV-24).
    """
    p = Prog()
    p.li("x10", 6)
    p.li("x11", 7)
    p.add("add x12, x10, x11")
    p.store("x12")

    state = run_program(tmp_path, "rv32i_sem_m", p.text(), rv32m=False,
                        requirements=["FR-RV-16", "FR-RV-24"])
    assert ram_slot(state, 0) == 13
    assert state["metrics"]["m_dispatches"] == 0


# ==========================================================================
# 10. Parada e travamento
# ==========================================================================

def test_travamento_e_detectado(tmp_path):
    """Um programa que nunca alcança o auto-laço tem de reprovar por teto de ciclos.

    Sem esta verificação, um "passou" poderia significar apenas que o
    testbench desistiu em silêncio (FR-RV-21).
    """
    asm = (
        "    li x1, 0x00FC8100\n"
        "    li x5, 0\n"
        "eterno:\n"
        "    addi x5, x5, 1\n"
        "    j eterno\n"
        "halt:\n"
        "    j halt\n"
    )
    # `cocotb_tools.runner.test` sinaliza reprovação com SystemExit, que é
    # BaseException e não seria pego por `Exception` sozinho.
    with pytest.raises((Exception, SystemExit)):
        run_program(tmp_path, "travado", asm, max_cycles=200,
                    requirements=["FR-RV-21"])
