"""Checks the public HDL contract before starting a costly simulation."""
from __future__ import annotations

import re
from pathlib import Path


REQUIRED_PORTS = {
    "clk": "in std_logic",
    "rst": "in std_logic",
    "instr_addr": "out std_logic_vector(31 downto 0)",
    "instr_data": "in std_logic_vector(31 downto 0)",
    "data_addr": "out std_logic_vector(31 downto 0)",
    "data_write": "out std_logic",
    "data_width": "out std_logic_vector(1 downto 0)",
    "data_write_data": "out std_logic_vector(31 downto 0)",
    "data_read_data": "in std_logic_vector(31 downto 0)",
}


def sources_for(cpu: Path) -> list[Path]:
    src = cpu / "src"
    sources = sorted(src.glob("*.vhd")) + sorted(src.glob("*.vhdl"))
    if not (src / "cpu.vhd").is_file():
        raise ValueError(f"{cpu}: falta src/cpu.vhd")
    if not sources:
        raise ValueError(f"{cpu}: não há fontes VHDL em src/")
    return sources


def validate_top(cpu: Path) -> Path:
    top = cpu / "src" / "cpu.vhd"
    cleaned = re.sub(r"--.*$", "", top.read_text(encoding="utf-8", errors="replace"), flags=re.M)
    entity = re.search(r"entity\s+cpu\s+is\s*port\s*\((.*?)\)\s*;?\s*end", cleaned,
                       flags=re.I | re.S)
    if not entity:
        raise ValueError(f"{top}: a entidade pública deve ser exatamente `cpu`")
    normal = re.sub(r"\s+", " ", entity.group(1)).lower()
    missing = [f"{name}: {kind}" for name, kind in REQUIRED_PORTS.items()
               if f"{name} : {kind}" not in normal]
    if missing:
        raise ValueError(f"{top}: contrato de specs/cpu.md incompatível; faltam/alteram: "
                         + ", ".join(missing))
    return top
