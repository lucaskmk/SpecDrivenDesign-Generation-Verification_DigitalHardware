"""Small, dependency-free ELF32 little-endian loader for RISC-V test images."""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path


class ElfError(ValueError):
    pass


@dataclass(frozen=True)
class Program:
    path: Path
    entry: int
    memory: dict[int, int]
    symbols: dict[str, int]


def load(path: str | Path) -> Program:
    path = Path(path)
    data = path.read_bytes()
    if len(data) < 52 or data[:4] != b"\x7fELF":
        raise ElfError(f"{path}: não é um ELF")
    if data[4] != 1 or data[5] != 1:
        raise ElfError(f"{path}: esperado ELF32 little-endian")
    header = struct.unpack_from("<16sHHIIIIIHHHHHH", data)
    _, _, machine, _, entry, phoff, shoff, _, _, phentsize, phnum, shentsize, shnum, shstrndx = header
    if machine != 243:
        raise ElfError(f"{path}: e_machine={machine}; esperado RISC-V (243)")
    memory: dict[int, int] = {}
    for index in range(phnum):
        off = phoff + index * phentsize
        if off + 32 > len(data):
            raise ElfError(f"{path}: cabeçalho de segmento truncado")
        kind, offset, vaddr, paddr, filesz, _, _, _ = struct.unpack_from("<IIIIIIII", data, off)
        if kind != 1:
            continue
        if offset + filesz > len(data):
            raise ElfError(f"{path}: segmento carregável truncado")
        base = paddr or vaddr
        memory.update({base + n: byte for n, byte in enumerate(data[offset:offset + filesz])})
    symbols = _symbols(data, shoff, shentsize, shnum, shstrndx)
    return Program(path=path, entry=entry, memory=memory, symbols=symbols)


def _symbols(data: bytes, shoff: int, shentsize: int, shnum: int, shstrndx: int) -> dict[str, int]:
    sections = []
    for index in range(shnum):
        off = shoff + index * shentsize
        if off + 40 > len(data):
            return {}
        sections.append(struct.unpack_from("<IIIIIIIIII", data, off))
    result: dict[str, int] = {}
    for _, kind, _, _, offset, size, link, _, _, entsize in sections:
        if kind != 2 or not entsize or link >= len(sections):  # SHT_SYMTAB
            continue
        str_offset, str_size = sections[link][4], sections[link][5]
        strings = data[str_offset:str_offset + str_size]
        for pos in range(offset, offset + size, entsize):
            if pos + 16 > len(data):
                break
            name_off, value, _, _, _, _ = struct.unpack_from("<IIIBBH", data, pos)
            if name_off >= len(strings):
                continue
            name = strings[name_off:].split(b"\0", 1)[0].decode("ascii", "replace")
            if name:
                result[name] = value
    return result
