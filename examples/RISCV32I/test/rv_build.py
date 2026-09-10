#!/usr/bin/env python3
"""Adaptador: monta um programa e manda o `rvverify` roda-lo no GHDL.

REQ: FR-RV-09 (imagem consumida pela ROM), FR-RV-21 (execucao real com exit
code), FR-RV-16 (selecao de RV32M por generic), NFR-RV-01 (GHDL + cocotb),
NFR-RV-02 (nada e declarado como medido sem executar a ferramenta).

O que MUDOU: a lista fixa de 20 arquivos VHDL, o mapa de memoria e a
mecanica de compilar/elaborar sairam daqui. A lista de fontes agora e o
campo `[design].sources` de `examples/RISCV32I/cpu.toml`; a compilacao com
cache e a chamada ao GHDL sao `rvverify.builder`.

O que NAO mudou: a API publica que as suites usam -- `run_program`,
`result_addr`, `RAM_BASE`, `run_builtin_snapshot`,
`materialize_original_sources`, `design_has_generic`.

Cada chamada de `run_program` dispara uma execucao real de `ghdl -r`. Se o
GHDL falhar ou o testbench reprovar, a chamada levanta excecao e o pytest
falha -- nenhum resultado e inferido do codigo gerado.

Nota de desempenho: o GHDL aplica generics na ELABORACAO, que no backend
mcode acontece em `ghdl -r`. Por isso o design e compilado uma unica vez por
arvore de fontes (cache em `rvverify.builder`) e cada programa e apenas uma
elaboracao nova com `-gROM_INIT_FILE=...`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, replace
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
REPO_ROOT = EXAMPLE_ROOT.parent.parent
SRC = EXAMPLE_ROOT / "src"
TOOLS = EXAMPLE_ROOT / "tools"
PROGRAMS = EXAMPLE_ROOT / "programs"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TOOLS))

from rv_assembler import (  # noqa: E402
    assemble_with_symbols,
    find_halt_addresses,
    write_ram_image,
)
from rvverify.builder import (  # noqa: E402
    build_design,
    design_declares_generic,
    run_simulation,
)
from rvverify.manifest import load_manifest  # noqa: E402

MANIFEST_PATH = EXAMPLE_ROOT / "cpu.toml"
MANIFEST = load_manifest(MANIFEST_PATH)

# Ordem de analise, agora derivada do manifesto (so os nomes de arquivo).
VHDL_ORDER = [Path(s).name for s in MANIFEST.design.sources]

# Enderecos de RAM usados pelos programas de teste para publicar resultados.
# Vem de [memory] do cpu.toml, que copia memory_package.vhd.
RAM_BASE = MANIFEST.memory.ram_base
RESULT_SLOT_0 = RAM_BASE
DATA_RAM_SIZE_BYTES = MANIFEST.memory.ram_bytes
STACK_TOP = RAM_BASE + DATA_RAM_SIZE_BYTES

DEFAULT_ROM_SIZE_WORDS = MANIFEST.program.size_words or 1024

ORIGINAL_REVISION = "f884a4e"
"""Commit que vendorizou o design RV32I original (ver decisions.md, ADR-000)."""


def _manifest_for(src_dir: Path | None):
    """Manifesto desta CPU, opcionalmente apontado para outra arvore de fontes.

    O manifesto declara as fontes como `src/<arquivo>.vhd`, relativas ao
    diretorio do exemplo. Uma arvore alternativa (o RTL ORIGINAL extraido do
    git por `materialize_original_sources`) e PLANA, so com os `.vhd`. Por
    isso, quando ha `src_dir`, os caminhos viram nomes de arquivo -- a ORDEM
    de analise, que e o que realmente importa, e preservada.
    """
    if src_dir is None:
        return MANIFEST
    flat = tuple(Path(s).name for s in MANIFEST.design.sources)
    return replace(MANIFEST, design=replace(MANIFEST.design, sources=flat))


def vhdl_sources(src_dir: Path | None = None) -> list[Path]:
    """Fontes existentes, na ordem de analise declarada no manifesto.

    `src_dir` aponta para uma arvore alternativa -- usada para materializar o
    RTL ORIGINAL a partir do git e comparar comportamento (FR-RV-07).
    """
    return _manifest_for(src_dir).source_paths(src_dir)


def result_addr(slot: int) -> int:
    """Endereco do slot de resultado `slot` (palavras de 32 bits)."""
    return RESULT_SLOT_0 + 4 * slot


def design_has_generic(generic_name: str, src_dir: Path | None = None) -> bool:
    """Descobre se a entidade de topo ja declara o generic pedido."""
    return design_declares_generic(_manifest_for(src_dir), generic_name, src_dir)


def ensure_build(src_dir: Path | None = None) -> tuple[Path, object]:
    """Compila o design uma vez e devolve (diretorio de build, runner).

    Mantida por compatibilidade com quem ja chamava esta funcao; o cache e a
    invalidacao por mudanca de fonte vivem em `rvverify.builder`.
    """
    built = build_design(_manifest_for(src_dir), src_dir=src_dir)
    return built.build_dir, built.runner


@dataclass
class ProgramRun:
    """Resultado de uma execucao real no GHDL."""

    name: str
    metrics: dict
    image_path: Path
    run_dir: Path
    waveform: Path | None

    @property
    def cycles(self) -> int:
        return self.metrics["cycles"]

    @property
    def instructions(self) -> int:
        return self.metrics["instructions"]

    @property
    def cpi(self) -> float | None:
        return self.metrics["cpi"]


def _run_dir(base: Path, name: str) -> Path:
    d = base / f"run_{name}"
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _rom_parameters(image: Path, rom_size_words: int, rv32m: bool,
                    src_dir: Path | None) -> dict[str, object]:
    """Generics de carga do programa e de configuracao, vindos do manifesto.

    O nome de cada generic esta em [program] do cpu.toml -- nada e literal
    aqui. `RV32M_ENABLE` so e passado se a arvore de fontes realmente o
    declara: o RTL original (FR-RV-07) nao tem esse generic, e passa-lo faria
    o GHDL recusar a elaboracao.
    """
    program = MANIFEST.program
    parameters: dict[str, object] = {}
    if program.generic:
        parameters[program.generic] = str(image)
    if program.size_generic:
        parameters[program.size_generic] = rom_size_words
    if design_has_generic("RV32M_ENABLE", src_dir):
        parameters["RV32M_ENABLE"] = "true" if rv32m else "false"
    return parameters


def run_program(
    tmp_path: Path,
    name: str,
    asm: str,
    *,
    expect_regs: dict[int, int] | None = None,
    expect_ram: dict[int, int] | None = None,
    max_cycles: int = 20000,
    rv32m: bool = False,
    allow_m: bool | None = None,
    requirements: list[str] | None = None,
    rom_size_words: int = DEFAULT_ROM_SIZE_WORDS,
    waves: bool = False,
    keep_image_at: Path | None = None,
    src_dir: Path | None = None,
    dump_ram: tuple[int, int] | None = None,
) -> ProgramRun:
    """Monta `asm`, grava a imagem `.ram` e executa a CPU no GHDL.

    `rv32m` seleciona o generic `RV32M_ENABLE` do design. Como o parametro da
    CHAMADA vence o manifesto, uma suite pode alternar as duas configuracoes
    caso a caso sem editar o `cpu.toml`.
    `allow_m` controla se o MONTADOR aceita instrucoes RV32M; por padrao
    acompanha `rv32m`, de modo que um programa de baseline nao consegue,
    nem por acidente, usar a extensao M (FR-RV-19).
    `dump_ram=(endereco, n_palavras)` faz o testbench devolver o conteudo da
    RAM em `metrics["ram_dump"]`, usado para provar que as versoes RV32I e
    RV32IM de um mesmo benchmark calculam o mesmo resultado (FR-RV-06).
    """
    if allow_m is None:
        allow_m = rv32m

    words, symbols = assemble_with_symbols(asm, base_address=0, allow_m=allow_m)
    if len(words) > rom_size_words:
        raise ValueError(
            f"programa {name!r} tem {len(words)} palavras, "
            f"maior que ROM_SIZE_WORDS={rom_size_words}"
        )

    # Enderecos de termino: instrucoes de auto-laco presentes na imagem.
    # REQ: FR-RV-21 -- termino deterministico, sem depender de PC estacionario
    # (a CPU resolve saltos em EX, ver ADR-000 e o campo [halt] do cpu.toml).
    halt_pcs = find_halt_addresses(words)
    if not halt_pcs:
        raise ValueError(
            f"programa {name!r} nao tem instrucao de parada. Termine o "
            f"programa com um auto-laco (`halt: j halt`), conforme a "
            f"convencao do ADR-003."
        )

    run_dir = _run_dir(tmp_path, name)
    image = write_ram_image(
        words,
        run_dir / f"{name}.ram",
        header=f"programa: {name}\n"
               f"requisitos: {', '.join(requirements or [])}\n"
               f"palavras: {len(words)}   parada em: "
               f"{', '.join(hex(p) for p in halt_pcs)}\n"
               f"gerado por examples/RISCV32I/tools/rv_assembler.py",
    )
    if keep_image_at is not None:
        keep_image_at.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(image, keep_image_at)

    metrics_out = run_dir / "metrics.json"
    spec = {
        "name": name,
        "image": str(image),
        "max_cycles": max_cycles,
        "rv32m_enable": rv32m,
        "requirements": requirements or [],
        "halt_pcs": halt_pcs,
        "symbols": symbols,
        "expect_regs": {str(k): v for k, v in (expect_regs or {}).items()},
        "expect_ram": {hex(k): v for k, v in (expect_ram or {}).items()},
        "metrics_out": str(metrics_out),
    }
    if dump_ram is not None:
        # (endereco inicial, quantidade de palavras) -- ver tb_program.py
        spec["dump_ram"] = {"start": dump_ram[0], "count": dump_ram[1]}
    spec_path = run_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    built = build_design(_manifest_for(src_dir), src_dir=src_dir)
    run_simulation(
        built,
        test_module="tb_program",
        parameters=_rom_parameters(image, rom_size_words, rv32m, src_dir),
        extra_env={"RV_PROGRAM_SPEC": str(spec_path)},
        python_paths=[HERE, TOOLS],
        waves=waves,
    )

    metrics = json.loads(metrics_out.read_text(encoding="utf-8"))

    wave_src = built.build_dir / f"{built.toplevel}.ghw"
    wave_dst: Path | None = None
    if waves and wave_src.exists():
        wave_dst = run_dir / f"{name}.ghw"
        shutil.move(str(wave_src), wave_dst)

    return ProgramRun(
        name=name,
        metrics=metrics,
        image_path=image,
        run_dir=run_dir,
        waveform=wave_dst,
    )


def run_builtin_snapshot(
    tmp_path: Path,
    name: str,
    *,
    cycles: int,
    rv32m: bool = False,
    src_dir: Path | None = None,
    requirements: list[str] | None = None,
) -> dict:
    """Roda o programa COMPILADO NA CONSTANTE VHDL por N ciclos e devolve o estado.

    REQ: FR-RV-07 (comprovar preservacao de comportamento), FR-RV-10 (o
    caminho da constante continua funcionando).

    Nao informa `ROM_INIT_FILE`, ou seja, exercita exatamente o caminho
    original do design (`INSTRUCTION_MEMORY_CONTENT`).

    `src_dir` permite rodar uma arvore de fontes alternativa (por exemplo o
    RTL original extraido do git) com este mesmo harness, o que torna a
    comparacao de comportamento um A/B de verdade.
    """
    run_dir = _run_dir(tmp_path, name)
    snapshot_out = run_dir / "snapshot.json"
    spec = {
        "name": name,
        "cycles": cycles,
        "requirements": requirements or [],
        "snapshot_out": str(snapshot_out),
    }
    spec_path = run_dir / "spec.json"
    spec_path.write_text(json.dumps(spec, indent=2), encoding="utf-8")

    parameters: dict[str, object] = {}
    if design_has_generic("RV32M_ENABLE", src_dir):
        parameters["RV32M_ENABLE"] = "true" if rv32m else "false"

    built = build_design(_manifest_for(src_dir), src_dir=src_dir)
    run_simulation(
        built,
        test_module="tb_snapshot",
        parameters=parameters,
        extra_env={"RV_PROGRAM_SPEC": str(spec_path)},
        python_paths=[HERE, TOOLS],
        waves=False,
    )

    return json.loads(snapshot_out.read_text(encoding="utf-8"))


def materialize_original_sources(dest: Path,
                                 revision: str = ORIGINAL_REVISION) -> Path:
    """Extrai do git o RTL ORIGINAL, antes das alteracoes desta trilha.

    REQ: FR-RV-07, NFR-RV-03 -- permite comparar o comportamento do design
    refatorado contra o original sob o mesmo testbench, em vez de confiar num
    snapshot anotado a mao. Os arquivos saem PLANOS em `dest`, e e por isso
    que `_manifest_for` achata os caminhos das fontes.
    """
    dest.mkdir(parents=True, exist_ok=True)
    prefix = EXAMPLE_ROOT.relative_to(REPO_ROOT).as_posix()
    for source in MANIFEST.design.sources:
        rel = f"{prefix}/{source}"
        proc = subprocess.run(
            ["git", "show", f"{revision}:{rel}"],
            cwd=REPO_ROOT, capture_output=True, text=True,
        )
        if proc.returncode != 0:
            continue          # arquivo nao existia no design original
        (dest / Path(source).name).write_text(proc.stdout, encoding="utf-8")
    return dest
