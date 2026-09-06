#!/usr/bin/env python3
"""Monta a biblioteca de benchmarks de `examples/RISCV32I/programs/`.

REQ: FR-RV-18 (benchmarks .c), FR-RV-19 (programas .asm, e prova de que os de
baseline são RV32I puro), FR-RV-20 (alternativa registrada à ausência de
compilador RISC-V), FR-RV-08 (formato de imagem documentado).

Cada `*.asm` do diretório vira uma imagem `*.ram` versionada ao lado, gerada
pelo montador do projeto (`rv_assembler.py`). A convenção de nome escolhe o
modo do montador, e é ela que dá a garantia pedida por FR-RV-19:

    *_rv32i.asm    -> allow_m=False   (o montador REJEITA qualquer RV32M)
    *_rv32im.asm   -> allow_m=True    (a extensão M é permitida)

Uso:
    python examples/RISCV32I/tools/build_programs.py
    python examples/RISCV32I/tools/build_programs.py --check

`--check` não escreve nada: só falha se alguma imagem versionada estiver
desatualizada em relação ao `.asm`. É o mesmo critério do teste
`test_programs.py::TestImagensVersionadas`.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXAMPLE_ROOT = HERE.parent
PROGRAMS = EXAMPLE_ROOT / "programs"

sys.path.insert(0, str(HERE))

from rv_assembler import (  # noqa: E402
    AssemblyError,
    assemble_with_symbols,
    find_halt_addresses,
    read_ram_image,
    write_ram_image,
)

RV32I_SUFFIX = "_rv32i.asm"
RV32IM_SUFFIX = "_rv32im.asm"


class ProgramError(Exception):
    """Programa que não monta, não segue a convenção de nome ou não para."""


@dataclass
class BuiltProgram:
    """Resultado da montagem de um `.asm` da biblioteca."""

    name: str
    source: Path
    image: Path
    words: list[int]
    halt_pcs: list[int]
    allow_m: bool

    @property
    def isa(self) -> str:
        return "RV32IM" if self.allow_m else "RV32I"

    @property
    def word_count(self) -> int:
        return len(self.words)


def allows_m(source: Path) -> bool:
    """Decide o modo do montador pelo sufixo do nome do arquivo."""
    name = source.name
    if name.endswith(RV32IM_SUFFIX):
        return True
    if name.endswith(RV32I_SUFFIX):
        return False
    raise ProgramError(
        f"{source.name}: nome fora da convenção; use `*{RV32I_SUFFIX}` ou "
        f"`*{RV32IM_SUFFIX}` para que o modo do montador seja explícito "
        f"(FR-RV-19)"
    )


def asm_sources(directory: Path | None = None) -> list[Path]:
    """Todos os `.asm` da biblioteca, em ordem determinística."""
    return sorted((directory or PROGRAMS).glob("*.asm"))


def image_path(source: Path, out_dir: Path | None = None) -> Path:
    """Caminho da imagem `.ram` correspondente a um `.asm`."""
    return (out_dir or source.parent) / (source.stem + ".ram")


def _header(source: Path, words: list[int], halt_pcs: list[int],
            allow_m: bool) -> str:
    """Cabeçalho de comentários da imagem. Sem data: precisa ser reprodutível."""
    return (
        f"programa: {source.stem}\n"
        f"fonte: examples/RISCV32I/programs/{source.name}\n"
        f"isa: {'RV32IM' if allow_m else 'RV32I (montado com allow_m=False)'}\n"
        f"palavras: {len(words)}   parada em: "
        f"{', '.join(hex(p) for p in halt_pcs)}\n"
        f"gerado por examples/RISCV32I/tools/build_programs.py\n"
        f"formato: uma palavra de 32 bits por linha, 8 digitos hex, "
        f"linha 0 = endereco 0x0 (ADR-003)"
    )


def assemble_source(source: Path) -> tuple[list[int], list[int], bool]:
    """Monta um `.asm` e devolve (palavras, endereços de parada, allow_m)."""
    allow_m = allows_m(source)
    text = source.read_text(encoding="utf-8")
    try:
        words, _symbols = assemble_with_symbols(text, base_address=0,
                                                allow_m=allow_m)
    except AssemblyError as e:
        raise ProgramError(f"{source.name}: {e}") from e

    halt_pcs = find_halt_addresses(words)
    if not halt_pcs:
        raise ProgramError(
            f"{source.name}: nenhuma instrução de parada. Termine o programa "
            f"com o auto-laço `halt: j halt` (ADR-003)"
        )
    return words, halt_pcs, allow_m


def build_one(source: Path, out_dir: Path | None = None,
              write: bool = True) -> BuiltProgram:
    """Monta um `.asm` e (por padrão) grava a imagem `.ram` ao lado."""
    words, halt_pcs, allow_m = assemble_source(source)
    out = image_path(source, out_dir)
    if write:
        write_ram_image(words, out, header=_header(source, words, halt_pcs,
                                                   allow_m))
    return BuiltProgram(
        name=source.stem,
        source=source,
        image=out,
        words=words,
        halt_pcs=halt_pcs,
        allow_m=allow_m,
    )


def build_all(directory: Path | None = None, out_dir: Path | None = None,
              write: bool = True) -> list[BuiltProgram]:
    """Monta toda a biblioteca. Levanta `ProgramError` no primeiro problema."""
    sources = asm_sources(directory)
    if not sources:
        raise ProgramError(
            f"nenhum programa .asm em {directory or PROGRAMS}"
        )
    return [build_one(s, out_dir=out_dir, write=write) for s in sources]


def stale_images(directory: Path | None = None) -> list[str]:
    """Imagens versionadas que não batem com o que o montador produz agora."""
    problems: list[str] = []
    for built in build_all(directory, write=False):
        if not built.image.exists():
            problems.append(f"{built.name}: imagem {built.image.name} não existe")
            continue
        try:
            stored = read_ram_image(built.image)
        except AssemblyError as e:
            problems.append(f"{built.name}: imagem ilegível ({e})")
            continue
        if stored != built.words:
            problems.append(
                f"{built.name}: imagem desatualizada "
                f"({len(stored)} palavras gravadas, {len(built.words)} montadas)"
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--programs-dir", type=Path, default=PROGRAMS,
                        help="diretório com os .asm (padrão: examples/RISCV32I/programs)")
    parser.add_argument("--check", action="store_true",
                        help="não grava nada; falha se alguma imagem estiver desatualizada")
    args = parser.parse_args(argv)

    try:
        if args.check:
            problems = stale_images(args.programs_dir)
            if problems:
                print("imagens .ram desatualizadas:", file=sys.stderr)
                for p in problems:
                    print(f"  - {p}", file=sys.stderr)
                print("rode: python examples/RISCV32I/tools/build_programs.py",
                      file=sys.stderr)
                return 1
            print(f"todas as imagens .ram de {args.programs_dir} estão atualizadas")
            return 0

        built = build_all(args.programs_dir)
    except ProgramError as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 1

    width = max(len(b.name) for b in built)
    print(f"{'programa'.ljust(width)}  {'isa':<6}  palavras  parada")
    print(f"{'-' * width}  {'-' * 6}  {'-' * 8}  {'-' * 12}")
    for b in built:
        halts = ", ".join(f"{p:#010x}" for p in b.halt_pcs)
        print(f"{b.name.ljust(width)}  {b.isa:<6}  {b.word_count:>8}  {halts}")
    print(f"\n{len(built)} programa(s) montado(s) em {args.programs_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
