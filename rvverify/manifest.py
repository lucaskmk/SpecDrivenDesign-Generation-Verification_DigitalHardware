#!/usr/bin/env python3
"""Leitura e validacao do `cpu.toml` -- o contrato entre uma CPU e o validador.

REQ: FR-RV-21 (execucao deterministica sob controle do testbench),
FR-RV-24 (metricas), NFR-RV-02 (nada e declarado como medido sem a
ferramenta correspondente).

O manifesto descreve TUDO o que o validador precisa saber sobre um design
para exercita-lo sem conhecer o RTL: como compila-lo, como aplicar clock e
reset, como carregar o programa, onde estao a RAM e o banco de registradores
e como reconhecer que o programa terminou.

O que este modulo NAO faz: adivinhar. Um campo obrigatorio ausente vira erro
com a mensagem dizendo qual campo, em qual tabela, em qual arquivo -- nunca um
valor default silencioso que produziria um resultado errado mais adiante.
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = [
    "ManifestError",
    "CpuManifest",
    "DesignSpec",
    "ClockSpec",
    "ResetSpec",
    "ProgramSpec",
    "MemorySpec",
    "ObserveSpec",
    "HaltSpec",
    "MetricsSpec",
    "load_manifest",
    "HALT_MODES",
    "PROGRAM_MODES",
    "MANIFEST_FILENAME",
]

MANIFEST_FILENAME = "cpu.toml"

HALT_MODES = ("commit_pc", "fetch_pc", "fixed_cycles")
PROGRAM_MODES = ("rom_init_file", "vhdl_constant")
RESET_POLARITIES = ("high", "low")

# Caminho de observacao: identificadores VHDL separados por ponto, do topo do
# DUT para dentro da hierarquia ("data_memory.data_ram.memory"). Indices,
# espacos e segmentos vazios sao recusados aqui, e nao la na frente com um
# AttributeError sem contexto.
_OBSERVE_PATH_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*(\.[A-Za-z_][A-Za-z_0-9]*)*$")


class ManifestError(ValueError):
    """O `cpu.toml` esta ausente, malformado ou incoerente."""


# --------------------------------------------------------------------------
# helpers de validacao
# --------------------------------------------------------------------------

def _table(raw: dict, name: str, where: str, *, required: bool) -> dict:
    value = raw.get(name)
    if value is None:
        if required:
            raise ManifestError(f"{where}: falta a tabela obrigatoria [{name}].")
        return {}
    if not isinstance(value, dict):
        raise ManifestError(
            f"{where}: [{name}] deveria ser uma tabela TOML, mas e "
            f"{type(value).__name__}."
        )
    return value


def _req(table: dict, key: str, section: str, where: str) -> Any:
    if key not in table:
        raise ManifestError(
            f"{where}: falta o campo obrigatorio `{key}` na tabela [{section}]."
        )
    return table[key]


def _as_str(value: Any, key: str, section: str, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(
            f"{where}: [{section}].{key} deveria ser uma string nao vazia, "
            f"mas e {value!r}."
        )
    return value


def _as_int(value: Any, key: str, section: str, where: str,
            *, minimum: int | None = None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestError(
            f"{where}: [{section}].{key} deveria ser um inteiro, mas e {value!r}."
        )
    if minimum is not None and value < minimum:
        raise ManifestError(
            f"{where}: [{section}].{key} = {value} e invalido; o minimo e {minimum}."
        )
    return value


def _as_choice(value: Any, key: str, section: str, where: str,
               choices: tuple[str, ...]) -> str:
    text = _as_str(value, key, section, where)
    if text not in choices:
        raise ManifestError(
            f"{where}: [{section}].{key} = {text!r} nao e reconhecido; "
            f"valores aceitos: {', '.join(choices)}."
        )
    return text


def _as_observe_path(value: Any, key: str, section: str, where: str) -> str:
    text = _as_str(value, key, section, where)
    if not _OBSERVE_PATH_RE.match(text):
        raise ManifestError(
            f"{where}: [{section}].{key} = {text!r} nao e um caminho de "
            f"observacao valido. Use identificadores VHDL separados por ponto, "
            f"do topo do DUT para dentro (por exemplo "
            f"data_memory.data_ram.memory); indices, espacos e segmentos "
            f"vazios nao sao aceitos."
        )
    return text


# --------------------------------------------------------------------------
# secoes
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DesignSpec:
    """[design] -- como compilar o RTL."""

    name: str
    top: str
    std: str
    sources: tuple[str, ...]
    generics: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ClockSpec:
    """[clock] -- sinal e periodo do relogio."""

    signal: str
    period_ns: int


@dataclass(frozen=True)
class ResetSpec:
    """[reset] -- sinal, polaridade e duracao do reset."""

    signal: str
    active: str = "high"
    cycles: int = 3

    @property
    def asserted(self) -> int:
        """Valor que ATIVA o reset, conforme a polaridade declarada."""
        return 1 if self.active == "high" else 0

    @property
    def released(self) -> int:
        """Valor que SOLTA o reset, conforme a polaridade declarada."""
        return 0 if self.active == "high" else 1


@dataclass(frozen=True)
class ProgramSpec:
    """[program] -- como o programa entra no design.

    `rom_init_file` passa o caminho da imagem `.ram` por generic, na
    ELABORACAO (o cocotb nao consegue escrever em ROM no GHDL -- ADR-003).
    `vhdl_constant` significa que o programa esta compilado no proprio RTL;
    nesse modo o validador so consegue rodar o programa embutido.
    """

    mode: str = "vhdl_constant"
    generic: str | None = None
    size_generic: str | None = None
    size_words: int | None = None

    @property
    def loadable(self) -> bool:
        """True quando da para carregar um programa arbitrario neste design."""
        return self.mode == "rom_init_file"


@dataclass(frozen=True)
class MemorySpec:
    """[memory] -- mapa da RAM de dados, para traduzir endereco em indice."""

    ram_base: int
    ram_bytes: int

    @property
    def ram_words(self) -> int:
        return self.ram_bytes // 4

    def contains(self, byte_addr: int) -> bool:
        return self.ram_base <= byte_addr < self.ram_base + self.ram_bytes

    def word_index(self, byte_addr: int) -> int:
        return (byte_addr - self.ram_base) // 4


@dataclass(frozen=True)
class ObserveSpec:
    """[observe] -- o que o validador consegue LER dentro do design.

    So `ram` e obrigatorio: sem ela nao ha como conferir resultado nenhum.
    O resto define ate onde a verificacao consegue ir (degradacao graciosa).
    Todo array observado tem de ser 1-D: o VPI do GHDL nao expoe arrays 2-D
    ao cocotb (ADR-002).
    """

    ram: str
    registers: str | None = None
    pc_fetch: str | None = None
    instr_fetch: str | None = None


@dataclass(frozen=True)
class HaltSpec:
    """[halt] -- como reconhecer que o programa terminou.

    `commit_pc`    pipeline com busca especulativa: o auto-laco so terminou
                   quando a propria instrucao de salto do endereco de parada
                   esta no estagio de commit E e tomada. Exige `pc` e `taken`.
    `fetch_pc`     monociclo/multiciclo sem especulacao: o PC de busca fica
                   ESTACIONARIO no auto-laco. Exige `pc`.
    `fixed_cycles` roda N ciclos e le a RAM. Sempre funciona, nao mede nada.
                   Exige `cycles`.
    """

    mode: str
    pc: str | None = None
    taken: str | None = None
    drain: int = 5
    cycles: int | None = None
    stationary: int = 2

    @property
    def measures_cycles(self) -> bool:
        """`fixed_cycles` nao observa termino: a contagem nao significa nada."""
        return self.mode != "fixed_cycles"


@dataclass(frozen=True)
class MetricsSpec:
    """[metrics] -- sinais opcionais de eficiencia. Tudo aqui pode faltar."""

    stall: str | None = None
    flush_d: str | None = None
    flush_f: str | None = None
    m_dispatch: str | None = None

    @property
    def declared(self) -> bool:
        return any((self.stall, self.flush_d, self.flush_f, self.m_dispatch))

    @property
    def can_derive_instructions(self) -> bool:
        """Instrucoes exigem os TRES sinais do pipeline; senao, seria chute."""
        return all((self.stall, self.flush_d, self.flush_f))

    def missing_for_instructions(self) -> list[str]:
        return [n for n, v in (("stall", self.stall),
                               ("flush_d", self.flush_d),
                               ("flush_f", self.flush_f)) if not v]


# --------------------------------------------------------------------------
# manifesto
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class CpuManifest:
    """O `cpu.toml` inteiro, ja validado."""

    path: Path
    root: Path
    design: DesignSpec
    clock: ClockSpec
    reset: ResetSpec
    program: ProgramSpec
    memory: MemorySpec
    observe: ObserveSpec
    halt: HaltSpec
    metrics: MetricsSpec

    # -- fontes ----------------------------------------------------------

    def source_paths(self, root: Path | None = None,
                     *, require_all: bool | None = None) -> list[Path]:
        """Fontes VHDL na ORDEM DE ANALISE declarada.

        `root` troca a arvore de fontes sem tocar no manifesto -- usado para
        rodar o mesmo testbench contra um RTL alternativo (por exemplo o
        original extraido do git). Nesse caso arquivos ausentes sao apenas
        ignorados, porque a arvore antiga pode nao ter todos os arquivos;
        na arvore declarada pelo manifesto, um arquivo ausente e erro.
        """
        base = Path(root) if root is not None else self.root
        strict = (root is None) if require_all is None else require_all
        out: list[Path] = []
        missing: list[str] = []
        for rel in self.design.sources:
            p = base / rel
            if p.exists():
                out.append(p.resolve())
            else:
                missing.append(rel)
        if strict and missing:
            raise ManifestError(
                f"{self.path}: [design].sources aponta para arquivo(s) que nao "
                f"existem em {base}: {', '.join(missing)}."
            )
        if not out:
            raise ManifestError(
                f"{self.path}: nenhuma fonte VHDL encontrada em {base}."
            )
        return out

    # -- generics --------------------------------------------------------

    def generics_for(self, overrides: dict[str, Any] | None = None) -> dict[str, Any]:
        """Generics do manifesto, sobrepostos pelos da chamada.

        Regra do contrato: o parametro da CHAMADA vence o manifesto -- as
        suites alternam configuracao (RV32M ligado/desligado) caso a caso.
        """
        merged: dict[str, Any] = dict(self.design.generics)
        merged.update(overrides or {})
        return merged

    # -- observabilidade -------------------------------------------------

    @property
    def observes_registers(self) -> bool:
        return self.observe.registers is not None

    def observability(self) -> dict[str, Any]:
        """O que este manifesto permite verificar, e o que NAO permite.

        REQ: NFR-RV-02 -- o relatorio precisa dizer explicitamente o que ficou
        sem observacao, em vez de omitir ou estimar.
        """
        unobserved: list[str] = []
        if not self.observes_registers:
            unobserved.append(
                "registradores: [observe].registers nao declarado; nenhuma "
                "assercao sobre xN e possivel"
            )
        if not self.metrics.can_derive_instructions:
            faltando = self.metrics.missing_for_instructions()
            unobserved.append(
                "instrucoes e CPI: [metrics] nao declara "
                + ", ".join(faltando)
                + "; sem esses sinais o numero de instrucoes nao e observavel"
            )
        if self.metrics.m_dispatch is None:
            unobserved.append(
                "instrucoes RV32M: [metrics].m_dispatch nao declarado"
            )
        if not self.halt.measures_cycles:
            unobserved.append(
                "ciclos ate o termino: [halt].mode = fixed_cycles roda um "
                "numero fixo de ciclos e nao observa o fim do programa"
            )
        return {
            "ram": True,
            "registers": self.observes_registers,
            "cycles": self.halt.measures_cycles,
            "instructions": self.metrics.can_derive_instructions,
            "m_instructions": self.metrics.m_dispatch is not None,
            "unobserved": unobserved,
        }

    # -- construcao ------------------------------------------------------

    @classmethod
    def from_dict(cls, raw: dict, path: Path,
                  root: Path | None = None) -> "CpuManifest":
        """Valida um dicionario ja lido do TOML. `path` so aparece nos erros."""
        where = str(path)
        base = Path(root) if root is not None else Path(path).parent

        design = _parse_design(raw, where)
        clock = _parse_clock(raw, where)
        reset = _parse_reset(raw, where)
        program = _parse_program(raw, where)
        memory = _parse_memory(raw, where)
        observe = _parse_observe(raw, where)
        halt = _parse_halt(raw, where)
        metrics = _parse_metrics(raw, where)

        return cls(
            path=Path(path), root=base, design=design, clock=clock, reset=reset,
            program=program, memory=memory, observe=observe, halt=halt,
            metrics=metrics,
        )


# --------------------------------------------------------------------------
# parsers por secao
# --------------------------------------------------------------------------

def _parse_design(raw: dict, where: str) -> DesignSpec:
    d = _table(raw, "design", where, required=True)
    sources = _req(d, "sources", "design", where)
    if not isinstance(sources, list) or not sources:
        raise ManifestError(
            f"{where}: [design].sources deveria ser uma lista nao vazia de "
            f"caminhos, NA ORDEM DE ANALISE."
        )
    for s in sources:
        if not isinstance(s, str) or not s.strip():
            raise ManifestError(
                f"{where}: [design].sources contem entrada invalida: {s!r}."
            )
    generics = d.get("generics", {})
    if not isinstance(generics, dict):
        raise ManifestError(f"{where}: [design.generics] deveria ser uma tabela TOML.")
    return DesignSpec(
        name=_as_str(_req(d, "name", "design", where), "name", "design", where),
        top=_as_str(_req(d, "top", "design", where), "top", "design", where),
        std=str(d.get("std", "08")),
        sources=tuple(sources),
        generics=dict(generics),
    )


def _parse_clock(raw: dict, where: str) -> ClockSpec:
    c = _table(raw, "clock", where, required=True)
    return ClockSpec(
        signal=_as_str(_req(c, "signal", "clock", where), "signal", "clock", where),
        period_ns=_as_int(_req(c, "period_ns", "clock", where),
                          "period_ns", "clock", where, minimum=1),
    )


def _parse_reset(raw: dict, where: str) -> ResetSpec:
    r = _table(raw, "reset", where, required=True)
    return ResetSpec(
        signal=_as_str(_req(r, "signal", "reset", where), "signal", "reset", where),
        active=_as_choice(r.get("active", "high"), "active", "reset", where,
                          RESET_POLARITIES),
        cycles=_as_int(r.get("cycles", 3), "cycles", "reset", where, minimum=1),
    )


def _parse_program(raw: dict, where: str) -> ProgramSpec:
    p = _table(raw, "program", where, required=False)
    program = ProgramSpec(
        mode=_as_choice(p.get("mode", "vhdl_constant"), "mode", "program", where,
                        PROGRAM_MODES),
        generic=_as_str(p["generic"], "generic", "program", where)
        if "generic" in p else None,
        size_generic=_as_str(p["size_generic"], "size_generic", "program", where)
        if "size_generic" in p else None,
        size_words=_as_int(p["size_words"], "size_words", "program", where, minimum=1)
        if "size_words" in p else None,
    )
    if program.mode == "rom_init_file" and not program.generic:
        raise ManifestError(
            f"{where}: [program].mode = rom_init_file exige [program].generic -- "
            f"o nome do generic que recebe o caminho da imagem. O cocotb nao "
            f"consegue escrever em ROM no GHDL, entao o programa precisa entrar "
            f"na elaboracao (ADR-003)."
        )
    return program


def _parse_memory(raw: dict, where: str) -> MemorySpec:
    m = _table(raw, "memory", where, required=True)
    ram_bytes = _as_int(_req(m, "ram_bytes", "memory", where),
                        "ram_bytes", "memory", where, minimum=4)
    if ram_bytes % 4:
        raise ManifestError(
            f"{where}: [memory].ram_bytes = {ram_bytes} nao e multiplo de 4; "
            f"a RAM observavel e um array de PALAVRAS de 32 bits."
        )
    return MemorySpec(
        ram_base=_as_int(_req(m, "ram_base", "memory", where),
                         "ram_base", "memory", where, minimum=0),
        ram_bytes=ram_bytes,
    )


def _parse_observe(raw: dict, where: str) -> ObserveSpec:
    o = _table(raw, "observe", where, required=True)
    return ObserveSpec(
        ram=_as_observe_path(_req(o, "ram", "observe", where), "ram", "observe", where),
        registers=_as_observe_path(o["registers"], "registers", "observe", where)
        if "registers" in o else None,
        pc_fetch=_as_observe_path(o["pc_fetch"], "pc_fetch", "observe", where)
        if "pc_fetch" in o else None,
        instr_fetch=_as_observe_path(o["instr_fetch"], "instr_fetch", "observe", where)
        if "instr_fetch" in o else None,
    )


def _parse_halt(raw: dict, where: str) -> HaltSpec:
    h = _table(raw, "halt", where, required=True)
    halt = HaltSpec(
        mode=_as_choice(_req(h, "mode", "halt", where), "mode", "halt", where,
                        HALT_MODES),
        pc=_as_observe_path(h["pc"], "pc", "halt", where) if "pc" in h else None,
        taken=_as_observe_path(h["taken"], "taken", "halt", where)
        if "taken" in h else None,
        drain=_as_int(h.get("drain", 5), "drain", "halt", where, minimum=0),
        cycles=_as_int(h["cycles"], "cycles", "halt", where, minimum=1)
        if "cycles" in h else None,
        stationary=_as_int(h.get("stationary", 2), "stationary", "halt", where,
                           minimum=1),
    )
    _validate_halt(halt, where)
    return halt


def _parse_metrics(raw: dict, where: str) -> MetricsSpec:
    mt = _table(raw, "metrics", where, required=False)
    return MetricsSpec(
        stall=_as_observe_path(mt["stall"], "stall", "metrics", where)
        if "stall" in mt else None,
        flush_d=_as_observe_path(mt["flush_d"], "flush_d", "metrics", where)
        if "flush_d" in mt else None,
        flush_f=_as_observe_path(mt["flush_f"], "flush_f", "metrics", where)
        if "flush_f" in mt else None,
        m_dispatch=_as_observe_path(mt["m_dispatch"], "m_dispatch", "metrics", where)
        if "m_dispatch" in mt else None,
    )


def _validate_halt(halt: HaltSpec, where: str) -> None:
    """Cada modo de parada exige os sinais que ele realmente le."""
    if halt.mode == "commit_pc":
        faltando = [k for k, v in (("pc", halt.pc), ("taken", halt.taken)) if not v]
        if faltando:
            nomes = " e ".join(f"`{k}`" for k in faltando)
            raise ManifestError(
                f"{where}: [halt].mode = commit_pc exige {nomes} em [halt]. "
                f"Nesse modo a parada e reconhecida por "
                f"pc == endereco_de_parada and taken == 1 no estagio de commit; "
                f"sem esses sinais nao ha como distinguir a execucao real do "
                f"auto-laco de uma busca especulativa."
            )
    elif halt.mode == "fetch_pc":
        if not halt.pc:
            raise ManifestError(
                f"{where}: [halt].mode = fetch_pc exige `pc` em [halt] -- o "
                f"sinal do PC de BUSCA, que fica estacionario no auto-laco. "
                f"Atencao: esse modo so vale para design SEM busca especulativa; "
                f"num pipeline especulativo o PC de busca passa pelo endereco de "
                f"parada a cada iteracao de laco e o resultado sai errado "
                f"(ADR-008)."
            )
    elif halt.mode == "fixed_cycles":
        if halt.cycles is None:
            raise ManifestError(
                f"{where}: [halt].mode = fixed_cycles exige `cycles` em [halt] -- "
                f"quantos ciclos rodar antes de ler a RAM."
            )


def load_manifest(path: str | Path) -> CpuManifest:
    """Carrega e valida um `cpu.toml`.

    Aceita o arquivo ou o diretorio que o contem.
    """
    p = Path(path)
    if p.is_dir():
        p = p / MANIFEST_FILENAME
    if not p.exists():
        raise ManifestError(
            f"manifesto nao encontrado: {p}. Toda CPU validada precisa de um "
            f"{MANIFEST_FILENAME} na raiz do seu diretorio."
        )
    try:
        raw = tomllib.loads(p.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as e:
        raise ManifestError(f"{p}: TOML invalido -- {e}") from e
    return CpuManifest.from_dict(raw, p.resolve())
