#!/usr/bin/env python3
# REQ: NFR-RV-05
"""Oraculo do montador: `rvverify.asm` conferido contra o binutils real.

REQ: NFR-RV-05 (imagem de container com assemblador RISC-V cruzado usada como
oraculo independente), FR-RV-19 (montador do projeto), ADR-004 (Revisao).

Por que existe: a ADR-004 escolheu escrever um montador em Python porque nao
havia toolchain RISC-V no ambiente, e registrou o risco disso -- um bug no
montador apareceria como falha de hardware. Os testes de encoding em
`cpus/rv32i_pipeline/test/test_toolchain.py` conferem o montador contra a
especificacao lida por uma pessoa. Este arquivo confere contra OUTRO programa:
o `riscv64-unknown-elf-as` do binutils, que ninguem neste projeto escreveu.

Como funciona: o mesmo `.asm` e montado duas vezes --

  1. por `rvverify.asm.assemble(...)`, em Python;
  2. dentro do container `spechdl-toolchain` (docker/Dockerfile), por
     `as` -> `ld` -> `objcopy -O binary`, lendo as palavras do binario
     little-endian --

e as duas listas de palavras de 32 bits sao comparadas uma a uma.

`ld` roda com `--relax` de proposito. Sem relaxacao, `as` expande `call` no par
canonico AUIPC+JALR, de alcance de 32 bits; a relaxacao o encolhe para um unico
JAL quando o alvo esta ao alcance, que e o que o montador deste projeto emite.
Rodar sem `--relax` faz os quatro programas com `call` divergirem por
construcao, e a divergencia seria sobre estrategia de expansao, nao sobre
encoding.

NFR-RV-05 exige que a ausencia da imagem apenas PULE a conferencia: sem Docker,
ou sem a imagem construida, todo teste daqui e pulado e a suite principal nao e
afetada. O montador Python continua sendo o caminho autocontido -- o binutils e
cross-check, nao substituto.

Como construir a imagem:
    docker build -t spechdl-toolchain -f docker/Dockerfile docker
"""

from __future__ import annotations

import shutil
import struct
import subprocess
from pathlib import Path

import pytest

from rvverify._ferramentas import PROGRAMS_DIR
from rvverify.asm import assemble, disassemble_word

IMAGE = "spechdl-toolchain"

# `as` com -march=rv32im e -mabi=ilp32: alvo de 32 bits, e o 'c' fica FORA do
# -march de proposito, porque a CPU so executa instrucoes de 32 bits.
# `ld` com -m elf32lriscv porque a emulacao padrao do binutils cruzado e de 64
# bits. --entry=0 silencia o aviso de _start ausente: estes programas nao sao
# executaveis hospedados, comecam no endereco 0.
_ORACLE_SH = r"""
set -e
cd /work
for f in *.asm; do
  b="${f%.asm}"
  riscv64-unknown-elf-as -march=rv32im -mabi=ilp32 -o "$b.o" "$f"
  riscv64-unknown-elf-ld -m elf32lriscv -Ttext=0x0 --entry=0 --relax \
      -o "$b.elf" "$b.o"
  riscv64-unknown-elf-objcopy -O binary "$b.elf" "$b.bin"
done
"""

# Um programa minimo por categoria de instrucao suportada, para cumprir o "pelo
# menos um programa de cada categoria" de NFR-RV-05: os benchmarks versionados
# exercitam combinacoes reais, mas nao cobrem toda instrucao individualmente.
CATEGORY_PROGRAMS: dict[str, str] = {
    "op_r_type": """
    add  x5, x6, x7
    sub  x5, x6, x7
    sll  x5, x6, x7
    slt  x5, x6, x7
    sltu x5, x6, x7
    xor  x5, x6, x7
    srl  x5, x6, x7
    sra  x5, x6, x7
    or   x5, x6, x7
    and  x5, x6, x7
""",
    "op_imm": """
    addi  x5, x6, -2048
    addi  x5, x6, 2047
    slti  x5, x6, -1
    sltiu x5, x6, 1
    xori  x5, x6, 255
    ori   x5, x6, -256
    andi  x5, x6, 15
    slli  x5, x6, 0
    slli  x5, x6, 31
    srli  x5, x6, 7
    srai  x5, x6, 31
""",
    "load": """
    lb  x5, 0(x6)
    lh  x5, 4(x6)
    lw  x5, -4(x6)
    lbu x5, 2047(x6)
    lhu x5, -2048(x6)
""",
    "store": """
    sb x5, 0(x6)
    sh x5, 4(x6)
    sw x5, -4(x6)
    sw x5, 2047(x6)
    sb x5, -2048(x6)
""",
    "branch": """
start:
    beq  x5, x6, start
    bne  x5, x6, start
    blt  x5, x6, ahead
    bge  x5, x6, ahead
    bltu x5, x6, ahead
    bgeu x5, x6, ahead
ahead:
    add  x0, x0, x0
""",
    "jump": """
target:
    jal  x1, target
    jal  x0, ahead
    jalr x1, 0(x2)
    jalr x0, -4(x2)
ahead:
    add  x0, x0, x0
""",
    "upper_immediate": """
    lui   x5, 0
    lui   x5, 1
    lui   x5, 0xFFFFF
    auipc x5, 0
    auipc x5, 0x12345
""",
    "rv32m": """
    mul    x5, x6, x7
    mulh   x5, x6, x7
    mulhsu x5, x6, x7
    mulhu  x5, x6, x7
    div    x5, x6, x7
    divu   x5, x6, x7
    rem    x5, x6, x7
    remu   x5, x6, x7
""",
}


def _docker_missing() -> str | None:
    """Motivo pelo qual o oraculo nao pode rodar, ou None se puder."""
    if shutil.which("docker") is None:
        return "docker nao esta no PATH"
    try:
        proc = subprocess.run(["docker", "image", "inspect", IMAGE],
                              capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:  # noqa: BLE001
        return f"docker nao respondeu: {e}"
    if proc.returncode != 0:
        return (f"imagem `{IMAGE}` nao existe; construa com "
                f"`docker build -t {IMAGE} -f docker/Dockerfile docker`")
    return None


_SKIP_REASON = _docker_missing()

pytestmark = pytest.mark.skipif(
    _SKIP_REASON is not None,
    reason=f"oraculo de montagem pulado (NFR-RV-05): {_SKIP_REASON}",
)


def _binutils_words(workdir: Path, sources: dict[str, str]) -> dict[str, list[int]]:
    """Monta cada fonte com o binutils real e devolve as palavras de `.text`.

    Uma unica invocacao de container para todos os fontes: subir um container
    por programa domina o tempo do teste.
    """
    for name, text in sources.items():
        (workdir / f"{name}.asm").write_text(text, encoding="utf-8")

    proc = subprocess.run(
        ["docker", "run", "--rm", "-v", f"{workdir}:/work", IMAGE,
         "bash", "-lc", _ORACLE_SH],
        capture_output=True, text=True, timeout=600,
    )
    assert proc.returncode == 0, (
        "o binutils do container falhou -- nao ha oraculo a comparar:\n"
        f"exit code: {proc.returncode}\nstdout:\n{proc.stdout}\n"
        f"stderr:\n{proc.stderr}"
    )

    out: dict[str, list[int]] = {}
    for name in sources:
        raw = (workdir / f"{name}.bin").read_bytes()
        assert raw, f"{name}: o binutils produziu um binario vazio"
        assert len(raw) % 4 == 0, (
            f"{name}: o binario do binutils tem {len(raw)} bytes, que nao e "
            f"multiplo de 4 -- alguma instrucao comprimida escapou do "
            f"-march=rv32im"
        )
        out[name] = list(struct.unpack(f"<{len(raw) // 4}I", raw))
    return out


def _compare(name: str, python_words: list[int], gnu_words: list[int]) -> None:
    """Compara palavra a palavra e falha com o encoding divergente a vista."""
    assert len(python_words) == len(gnu_words), (
        f"{name}: o montador Python produziu {len(python_words)} palavras e o "
        f"binutils {len(gnu_words)}. Diferenca de TAMANHO e quase sempre "
        f"expansao de pseudo-instrucao divergente, nao encoding errado."
    )
    divergent = [
        (i, py, gnu)
        for i, (py, gnu) in enumerate(zip(python_words, gnu_words))
        if py != gnu
    ]
    assert not divergent, (
        f"{name}: {len(divergent)} de {len(python_words)} palavras divergem "
        f"entre rvverify/asm.py e riscv64-unknown-elf-as (NFR-RV-05).\n"
        + "\n".join(
            f"  palavra {i} (endereco {4 * i:#06x}): "
            f"python={py:#010x} ({disassemble_word(py)}) != "
            f"binutils={gnu:#010x} ({disassemble_word(gnu)})"
            for i, py, gnu in divergent[:20]
        )
    )


def _versioned_names() -> list[str]:
    return sorted(p.stem for p in PROGRAMS_DIR.glob("*.asm"))


@pytest.fixture(scope="module")
def versioned_programs() -> dict[str, tuple[str, bool]]:
    """Os `.asm` versionados, com o modo do montador que cada nome implica."""
    sources = {
        p.stem: (p.read_text(encoding="utf-8"), p.name.endswith("_rv32im.asm"))
        for p in sorted(PROGRAMS_DIR.glob("*.asm"))
    }
    assert sources, f"nenhum .asm em {PROGRAMS_DIR}"
    return sources


@pytest.fixture(scope="module")
def versioned_oracle(tmp_path_factory, versioned_programs):
    workdir = tmp_path_factory.mktemp("oracle_programs")
    return _binutils_words(
        workdir, {name: text for name, (text, _) in versioned_programs.items()}
    )


@pytest.fixture(scope="module")
def category_oracle(tmp_path_factory):
    workdir = tmp_path_factory.mktemp("oracle_categories")
    return _binutils_words(workdir, CATEGORY_PROGRAMS)


class TestProgramasVersionados:
    """Os benchmarks reais do repositorio, conferidos contra o binutils."""

    @pytest.mark.parametrize("name", _versioned_names())
    def test_palavra_a_palavra(self, name, versioned_programs, versioned_oracle):
        text, allow_m = versioned_programs[name]
        python_words = assemble(text, base_address=0, allow_m=allow_m)
        _compare(name, python_words, versioned_oracle[name])


class TestCategoriasDeInstrucao:
    """Uma categoria de instrucao por programa, como NFR-RV-05 pede."""

    @pytest.mark.parametrize("name", sorted(CATEGORY_PROGRAMS))
    def test_palavra_a_palavra(self, name, category_oracle):
        python_words = assemble(CATEGORY_PROGRAMS[name], base_address=0,
                                allow_m=True)
        assert python_words, f"{name}: o montador Python nao produziu palavra alguma"
        _compare(name, python_words, category_oracle[name])


def test_o_oraculo_detecta_divergencia():
    """Guarda do proprio oraculo: uma palavra trocada TEM de reprovar.

    Sem isto, um erro que fizesse `_compare` comparar listas vazias passaria
    despercebido e o oraculo viraria decoracao.
    """
    with pytest.raises(AssertionError, match="divergem"):
        _compare("sintetico", [0x00000013, 0x00000013], [0x00000013, 0x00000033])
    with pytest.raises(AssertionError, match="TAMANHO"):
        _compare("sintetico", [0x00000013], [0x00000013, 0x00000013])
