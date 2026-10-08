"""Montagem restrita de estímulos RISC-V para testbenches Cocotb.

A LLM pode descrever assembly, mas nunca deve calcular os campos binários de
uma instrução. Este módulo usa o GNU assembler como autoridade externa e
retorna uma imagem de memória de instruções indexada por PC.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path


class ErroAssemblyRV32I(ValueError):
    """Assembly não é um programa RV32I mínimo e seguro para um teste."""


_MNEMONICOS_RV32I = {
    "lui", "auipc", "jal", "jalr",
    "beq", "bne", "blt", "bge", "bltu", "bgeu",
    "lb", "lh", "lw", "lbu", "lhu", "sb", "sh", "sw",
    "addi", "slti", "sltiu", "xori", "ori", "andi", "slli", "srli", "srai",
    "add", "sub", "sll", "slt", "sltu", "xor", "srl", "sra", "or", "and",
    "fence", "fence.i", "ecall", "ebreak",
}
_MNEMONICOS_RV32M = {"mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"}
_ROTULO = re.compile(r"[A-Za-z_.$][A-Za-z0-9_.$]*:")
_ALVO_NUMERICO = re.compile(r"[-+]?(?:0x[0-9a-fA-F]+|\d+)$")


def _ferramenta(nome: str) -> str:
    for prefixo in ("riscv64-unknown-elf", "riscv32-unknown-elf"):
        if caminho := shutil.which(f"{prefixo}-{nome}"):
            return caminho
    raise ErroAssemblyRV32I(
        "binutils RISC-V ausente: instale riscv64-unknown-elf-as/objcopy "
        "ou use a imagem spechdl-toolchain")


def _mnemonicos_da_isa(isa: str) -> set[str]:
    if isa == "rv32i":
        return _MNEMONICOS_RV32I
    if isa == "rv32im":
        return _MNEMONICOS_RV32I | _MNEMONICOS_RV32M
    raise ErroAssemblyRV32I(f"ISA sem capacidade de assembly configurada: {isa}")


def validar_assembly_riscv(fonte: str, *, isa: str = "rv32i",
                           exigir_labels_controle: bool = False) -> None:
    """Aceita labels locais e mnemonics reais do perfil RISC-V configurado."""
    mnemonicos = _mnemonicos_da_isa(isa)
    for numero, bruta in enumerate(fonte.splitlines(), 1):
        linha = bruta.split("#", 1)[0].strip()
        if not linha:
            continue
        while (m := _ROTULO.match(linha)):
            linha = linha[m.end():].strip()
        if not linha:
            continue
        if linha.startswith("."):
            raise ErroAssemblyRV32I(f"linha {numero}: diretivas assembly não são permitidas")
        mnemonic = linha.split(None, 1)[0].lower()
        if mnemonic not in mnemonicos:
            raise ErroAssemblyRV32I(
                f"linha {numero}: {mnemonic!r} não é uma instrução {isa.upper()} permitida")
        if exigir_labels_controle and mnemonic in {"jal", "beq", "bne", "blt", "bge", "bltu", "bgeu"}:
            operandos = [p.strip() for p in linha[len(mnemonic):].split(",")]
            if operandos and _ALVO_NUMERICO.fullmatch(operandos[-1]):
                raise ErroAssemblyRV32I(
                    f"linha {numero}: use um label como alvo de {mnemonic}, não deslocamento numérico")


def assemble_riscv(fonte: str, *, isa: str = "rv32i",
                    exigir_labels_controle: bool = False) -> dict[int, int]:
    """Monta ``fonte`` RV32I e devolve ``{pc: palavra_uint32}``.

    Labels são resolvidos pelo assembler. Diretivas e pseudoinstruções são
    rejeitadas deliberadamente: cada linha não-vazia deve representar uma
    instrução RV32I real, mantendo o programa de teste pequeno e auditável.
    """
    validar_assembly_riscv(fonte, isa=isa, exigir_labels_controle=exigir_labels_controle)
    assembler, objcopy = _ferramenta("as"), _ferramenta("objcopy")
    with tempfile.TemporaryDirectory(prefix="rvgen-rv32i-") as temporario:
        raiz = Path(temporario)
        src, obj, binario = raiz / "programa.s", raiz / "programa.o", raiz / "programa.bin"
        src.write_text(".option norvc\n.option norelax\n.text\n" + fonte + "\n", encoding="utf-8")
        try:
            subprocess.run([assembler, f"-march={isa}", "-mabi=ilp32", "-o", str(obj), str(src)],
                           check=True, text=True, capture_output=True, timeout=10)
            subprocess.run([objcopy, "-O", "binary", "--only-section=.text", str(obj), str(binario)],
                           check=True, text=True, capture_output=True, timeout=10)
        except subprocess.CalledProcessError as e:
            texto = (e.stderr or e.stdout or "erro desconhecido").strip()
            raise ErroAssemblyRV32I(f"GNU assembler recusou o programa RV32I: {texto}") from e
        dados = binario.read_bytes()
    if not dados or len(dados) % 4:
        raise ErroAssemblyRV32I("programa RV32I não produziu palavras de 32 bits")
    return {pc: int.from_bytes(dados[pc:pc + 4], "little")
            for pc in range(0, len(dados), 4)}


def validar_assembly_rv32i(fonte: str, *, exigir_labels_controle: bool = False) -> None:
    """Compatibilidade para o perfil RV32I."""
    validar_assembly_riscv(fonte, isa="rv32i", exigir_labels_controle=exigir_labels_controle)


def validar_assembly_rv32im(fonte: str, *, exigir_labels_controle: bool = False) -> None:
    """Valida estímulos RV32IM, incluindo a extensão M."""
    validar_assembly_riscv(fonte, isa="rv32im", exigir_labels_controle=exigir_labels_controle)


def assemble_rv32i(fonte: str, *, exigir_labels_controle: bool = False) -> dict[int, int]:
    return assemble_riscv(fonte, isa="rv32i", exigir_labels_controle=exigir_labels_controle)


def assemble_rv32im(fonte: str, *, exigir_labels_controle: bool = False) -> dict[int, int]:
    return assemble_riscv(fonte, isa="rv32im", exigir_labels_controle=exigir_labels_controle)
