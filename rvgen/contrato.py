#!/usr/bin/env python3
"""O contrato fixo da CPU gerada e o `cpu.toml` dela.

REQ: FR-RV-47 (ISAs aceitas e contrato determinístico), FR-RV-05, FR-RV-06,
FR-RV-09, FR-RV-15, FR-RV-16.

A ideia central: tudo o que NAO precisa de IA nao passa por IA. O modelo so
escreve VHDL. O top-level, os nomes que o testbench le por hierarquia e o
manifesto sao fixados aqui -- o mesmo contrato que um aluno recebe em
`entregas/README.md`, com os nomes escolhidos de antemao. Assim o `cpu.toml`
sai sempre certo, e o modelo nao gasta iteracao adivinhando caminho de
observacao.

As interfaces de suporte ainda são lidas para testes isolados de componentes.
"""

from __future__ import annotations

import os
import re
from pathlib import Path, PurePosixPath

from rvverify.memmap import RAM_BASE, RAM_BYTES

from .config import REPO_ROOT

__all__ = [
    "ErroContrato",
    "ISAS",
    "TOP",
    "FORNECIDOS",
    "FORNECIDOS_DIR",
    "ENTIDADES_RESERVADAS",
    "VAR_SPECS",
    "pasta_specs",
    "pasta_specs_alterada",
    "descrever_pasta_specs",
    "validar_isa",
    "declaracoes_de_entidade",
    "verificar_contrato",
    "interfaces_fornecidas",
    "texto_do_contrato",
    "texto_de_testes",
    "renderizar_cpu_toml",
    "ler_configuracao_cpu",
    "instrucoes_da_isa",
]

TOP = "cpu"
ISAS = ("rv32i", "rv32im")

FORNECIDOS_DIR = REPO_ROOT / "cpus" / "rv32i_pipeline" / "src"
# Caminhos padrao (specs/ da raiz). O que o rvgen le de fato vem de
# pasta_specs(), que respeita RVGEN_SPECS_DIR.
SPECS_DIR = REPO_ROOT / "specs"
VHDL_SPEC = SPECS_DIR / "vhdl.md"
CPU_SPEC = SPECS_DIR / "cpu.md"
RV32I_SPEC = SPECS_DIR / "riscv-rv32i.md"
TESTES_SPEC = SPECS_DIR / "testes.md"
VAR_SPECS = "RVGEN_SPECS_DIR"
_ISA_CPU_RE = re.compile(r"\bRV32I(?:M)?\b", re.IGNORECASE)
_MICROARQUITETURAS_CPU_RE = {
    "monociclo": re.compile(r"\bsingle[- ]cycle\b", re.IGNORECASE),
    "multiciclo": re.compile(r"\bmulticycle\b", re.IGNORECASE),
    "pipeline": re.compile(r"\bpipeline\b", re.IGNORECASE),
}
# Ordem de ANALISE: pacotes antes de quem os usa (a mesma de entregas/_modelo).
FORNECIDOS = (
    "cpu_package.vhd",
    "memory_package.vhd",
    "data_ram.vhd",
    "data_rom.vhd",
    "data_memory.vhd",
    "instruction_memory.vhd",
)
# Nomes que o modelo nao pode reusar: ja existem na biblioteca `work`.
ENTIDADES_RESERVADAS = frozenset({
    "cpu_package", "memory_package", "data_ram", "data_rom",
    "data_memory", "instruction_memory",
})


class ErroContrato(ValueError):
    """ISA ou contrato fora do escopo do validador oficial."""


def validar_isa(isa: str) -> None:
    """Recusa uma ISA que ``spec-riscv-test`` ainda não sabe validar."""
    if isa not in ISAS:
        raise ErroContrato(
            f"ISA {isa!r} nao e julgada pelo spec-riscv-test; aceitas: {', '.join(ISAS)}. "
            f"Outra extensao exige primeiro estender o validador (spec, modelo "
            f"de referencia, montador e casos)."
        )


def pasta_specs() -> Path:
    """A pasta dos .md que o rvgen le, resolvida a cada chamada.

    ``RVGEN_SPECS_DIR`` (absoluta ou relativa a raiz do repositorio) troca
    ``specs/`` por outra pasta, por exemplo uma iteracao em
    ``iteracoes/it-002/specs``. Sem a variavel, vale ``specs/``.
    """
    valor = os.environ.get(VAR_SPECS, "").strip()
    if not valor:
        return SPECS_DIR
    pasta = Path(valor)
    if not pasta.is_absolute():
        pasta = REPO_ROOT / pasta
    return pasta.resolve()


def pasta_specs_alterada() -> bool:
    """True quando ``RVGEN_SPECS_DIR`` esta definida (nao vazia)."""
    return bool(os.environ.get(VAR_SPECS, "").strip())


def descrever_pasta_specs() -> str:
    """``pasta_specs()`` relativa a raiz (POSIX) quando estiver dentro dela."""
    pasta = pasta_specs()
    try:
        return pasta.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        return str(pasta)


def _arquivo_spec(nome: str, pasta: Path | None) -> Path:
    return Path(pasta if pasta is not None else pasta_specs()) / nome


def ler_configuracao_cpu(caminho: Path | None = None, *, pasta: Path | None = None) -> dict:
    """Infere ISA e microarquitetura do texto em ``specs/cpu.md``.

    Sem ``caminho``, le o ``cpu.md`` de ``pasta`` (ou de ``pasta_specs()``).
    """
    if caminho is None:
        caminho = _arquivo_spec("cpu.md", pasta)
    try:
        texto = caminho.read_text(encoding="utf-8")
    except OSError as e:
        raise ErroContrato(f"nao foi possivel ler a especificacao da CPU {caminho}: {e}") from e
    isas = {m.group(0).lower() for m in _ISA_CPU_RE.finditer(texto)}
    microarquiteturas = {nome for nome, padrao in _MICROARQUITETURAS_CPU_RE.items()
              if padrao.search(texto)}
    if len(isas) != 1:
        raise ErroContrato(
            f"{caminho}: declare exatamente uma ISA reconhecida (RV32I ou RV32IM)"
        )
    if len(microarquiteturas) != 1:
        raise ErroContrato(
            f"{caminho}: declare exatamente uma microarquitetura reconhecida "
            "(single cycle, multicycle ou pipeline)"
        )
    isa, microarquitetura = isas.pop(), microarquiteturas.pop()
    validar_isa(isa)
    return {"microarquitetura": microarquitetura, "isa": isa, "descricao": None}


# --------------------------------------------------------------------------
# o que o modelo le
# --------------------------------------------------------------------------

_ENTIDADE_RE = re.compile(r"^[ \t]*entity\s+(\w+)\s+is\b.*?^[ \t]*end\b[^;]*;",
                          re.IGNORECASE | re.MULTILINE | re.DOTALL)


def declaracoes_de_entidade(texto: str) -> list[str]:
    """Os blocos `entity ... end ...;` de um texto VHDL."""
    return [m.group(0).strip() for m in _ENTIDADE_RE.finditer(texto)]


def _sem_comentarios(texto: str) -> str:
    linhas = [ln.rstrip() for ln in texto.splitlines()
              if ln.strip() and not ln.strip().startswith("--")]
    return "\n".join(linhas)


def interfaces_fornecidas(diretorio: Path = FORNECIDOS_DIR) -> str:
    """O pacote de tipos inteiro, as constantes do mapa de memoria e as
    entidades fornecidas -- tudo lido dos arquivos reais."""
    partes = ["-- cpu_package.vhd (types and constants you must use)",
              _sem_comentarios((diretorio / "cpu_package.vhd").read_text(encoding="utf-8"))]
    mem = (diretorio / "memory_package.vhd").read_text(encoding="utf-8")
    constantes = [ln.strip() for ln in mem.splitlines()
                  if re.match(r"\s*constant\s+\w+\s*:\s*integer", ln, re.IGNORECASE)]
    partes += ["-- memory_package.vhd (integer constants of the memory map)",
               "\n".join(constantes)]
    for arquivo in ("instruction_memory.vhd", "data_memory.vhd"):
        texto = (diretorio / arquivo).read_text(encoding="utf-8")
        for decl in declaracoes_de_entidade(texto):
            partes += [f"-- {arquivo}", decl]
    return "\n\n".join(partes)


_RV32I = ("lui auipc jal jalr beq bne blt bge bltu bgeu lb lh lw lbu lhu sb sh sw "
          "addi slti sltiu xori ori andi slli srli srai "
          "add sub sll slt sltu xor srl sra or and")
_RV32M = "mul mulh mulhsu mulhu div divu rem remu"


def instrucoes_da_isa(isa: str) -> tuple[str, ...]:
    """Mnemônicos que a arquitetura deve documentar e implementar."""
    validar_isa(isa)
    return tuple(_RV32I.split()) + (tuple(_RV32M.split()) if isa == "rv32im" else ())


def texto_do_contrato(microarquitetura: str, isa: str, pasta: Path | None = None) -> str:
    """O prompt de sistema: o contrato inteiro, em ingles.

    Le cpu.md, vhdl.md e riscv-rv32i.md de ``pasta`` (ou de ``pasta_specs()``).
    """
    vhdl_spec = _arquivo_spec("vhdl.md", pasta)
    rv32i_spec = _arquivo_spec("riscv-rv32i.md", pasta)
    cpu_spec_arq = _arquivo_spec("cpu.md", pasta)
    if isa == "rv32im":
        extensao = (
            f"RV32M ({_RV32M}) is required: decode opcode 0110011 with "
            f"funct7 = 0000001. Implement these operations in generated VHDL, "
            f"including RISC-V division-by-zero and signed-overflow semantics. "
            f"The entity `cpu` has no generics: the ISA is fixed by "
            f"specs/cpu.md, so the CPU always implements the M instructions."
        )
    else:
        extensao = ("RV32M is NOT required, and the entity `cpu` has no "
                     "generics: do not add one.")
    try:
        regras_vhdl = vhdl_spec.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ErroContrato(f"nao foi possivel ler a especificacao VHDL {vhdl_spec}: {e}") from e
    try:
        referencia_rv32i = rv32i_spec.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ErroContrato(f"nao foi possivel ler a referencia RV32I {rv32i_spec}: {e}") from e
    try:
        cpu_spec = cpu_spec_arq.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ErroContrato(f"nao foi possivel ler a especificacao da CPU {cpu_spec_arq}: {e}") from e
    valores = {
        "{{PROVIDED_FILES}}": ", ".join(FORNECIDOS),
        "{{TOP}}": TOP,
        "{{PROVIDED_DECLARATIONS}}": interfaces_fornecidas(),
    }
    for marcador, valor in valores.items():
        cpu_spec = cpu_spec.replace(marcador, valor)
    detalhes_derivados = f"""# Requirements derived from the CPU declaration
ISA base: RV32I ({_RV32I}).
{extensao}
Microarchitecture declared in specs/cpu.md: {microarquitetura}.
"""
    return f"""You write VHDL for a RISC-V CPU that an automatic conformance suite
    (GHDL + cocotb, the `spec-riscv-test` validator) will judge by running
    official real RISC-V programs. Follow this
contract exactly: a CPU that deviates from it cannot be observed and fails.

# CPU Specification
{cpu_spec}

{detalhes_derivados}

# RV32I Implementation Reference
{referencia_rv32i}

# Essential VHDL Generation Specification
You MUST follow this specification.
{regras_vhdl}
"""


def texto_de_testes(pasta: Path | None = None) -> str:
    """Regras versionadas para as chamadas que escrevem Cocotb, somente."""
    testes_spec = _arquivo_spec("testes.md", pasta)
    try:
        return testes_spec.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ErroContrato(f"nao foi possivel ler as regras de teste {testes_spec}: {e}") from e


_PORTAS_CPU = ("clk", "rst", "instr_addr", "instr_data", "data_addr", "data_write",
               "data_width", "data_write_data", "data_read_data")


def _sem_comentarios_vhdl(texto: str) -> str:
    return "\n".join(ln.split("--", 1)[0] for ln in texto.splitlines())


def _instancias(texto: str) -> dict[str, str]:
    """{rotulo: entidade} das instancias `rotulo : entity work.x` e de componente."""
    out: dict[str, str] = {}
    for m in re.finditer(r"(?im)^\s*(\w+)\s*:\s*entity\s+\w+\.(\w+)", texto):
        out[m.group(1).lower()] = m.group(2).lower()
    for m in re.finditer(r"(?is)(?:^|\n)\s*(\w+)\s*:\s*(\w+)\s+(?:generic|port)\s+map", texto):
        if m.group(2).lower() not in ("entity", "in", "out", "inout", "buffer"):
            out.setdefault(m.group(1).lower(), m.group(2).lower())
    return out


def verificar_contrato(fontes: dict[str, str]) -> list[tuple[str, str]]:
    """Divergencias do contrato visiveis no texto das fontes, antes do GHDL.

    REQ: FR-RV-48. Inspecao estatica por expressao regular: aponta o que o
    GHDL ou o testbench vao reclamar depois -- um rotulo de instancia errado
    so aparece como "caminho de observacao inexistente" DEPOIS de compilar,
    e um acesso hierarquico da um erro de compilacao que o modelo local nao
    soube ler (TRV-9.8). Devolve (arquivo, aviso em ingles, para o prompt).
    E sugestao: nunca muda o veredito, que é só da suíte oficial.
    """
    arq_top = f"src/{TOP}.vhd"
    top = _sem_comentarios_vhdl(fontes.get(arq_top, ""))
    avisos: list[tuple[str, str]] = []
    if not re.search(rf"(?i)\bentity\s+{TOP}\s+is\b", top):
        return [(arq_top, f"{arq_top} does not declare `entity {TOP}`.")]
    for porta in _PORTAS_CPU:
        if not re.search(rf"(?i)\b{porta}\s*:", top):
            avisos.append((arq_top, f"{TOP} must declare the port `{porta}`."))
    return avisos


# --------------------------------------------------------------------------
# o manifesto
# --------------------------------------------------------------------------

def _relativo(alvo: Path, pasta: Path) -> str:
    """Caminho de `alvo` visto de `pasta`, com barras POSIX (vale no Docker)."""
    try:
        rel = os.path.relpath(alvo.resolve(), pasta.resolve())
    except ValueError:                       # outra unidade no Windows
        return alvo.resolve().as_posix()
    return PurePosixPath(*Path(rel).parts).as_posix()


def _toml(valor: object) -> str:
    if isinstance(valor, bool):
        return "true" if valor else "false"
    if isinstance(valor, int):
        return str(valor)
    return '"' + str(valor).replace("\\", "\\\\").replace('"', '\\"') + '"'


def renderizar_cpu_toml(nome: str, pasta: Path, isa: str,
                        arquivos: list[str]) -> str:
    """O `cpu.toml` da entrega. Nenhum campo vem do modelo."""
    fontes = list(arquivos)
    linhas = [
        "# Manifesto gerado por rvgen (FR-RV-47): deterministico, a partir do",
        "# contrato fixo em rvgen/contrato.py. Nao foi escrito",
        "# pelo modelo de linguagem; so as fontes em src/ foram.",
        "#",
        "# REQ: FR-RV-05, FR-RV-06, FR-RV-09, FR-RV-15, FR-RV-16, FR-RV-21",
        "",
        "[design]",
        f"name = {_toml(nome)}",
        f"top  = {_toml(TOP)}",
        'std  = "08"',
    ]
    if isa == "rv32im":
        linhas.append('rv32m_generic = "RV32M_ENABLE"')
    linhas.append("sources = [")
    linhas += [f"    {_toml(f)}," for f in fontes]
    linhas += [
        "]",
        "",
        "[clock]",
        'signal    = "clk"',
        "period_ns = 10",
        "",
        "[reset]",
        'signal = "rst"',
        'active = "high"',
        "cycles = 3",
        "",
        "[program]",
        'mode         = "virtual"',
        "size_words   = 1024",
        "",
        "[memory]",
        f"ram_base  = {RAM_BASE:#010x}",
        f"ram_bytes = {RAM_BYTES}",
        "",
        "[observe]",
        'ram       = "virtual"',
    ]
    linhas += ["", "[halt]", 'mode = "fetch_pc"', 'pc = "instr_addr"',
               "stationary = 2", "drain = 2", "", "[metrics]"]
    return "\n".join(linhas) + "\n"
