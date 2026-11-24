#!/usr/bin/env python3
"""Combinado entre blocos: `python -m rvgen interfaces <cpu>`.

Checagem sem IA de um tipo de defeito que só o juiz final pegava: dois
blocos que combinam códigos diferentes num sinal de seleção. Caso real
(`luna6_abl_m_reduzida_4`, 23/11/2026): a `control_unit` mandava `alu_op`
de `10000` a `10110` para as operações do M, e a `alu` só decodificava até
`10001`; cada bloco passava nos próprios testes e a CPU tirou 1/48.

Para cada sinal do topo que liga uma porta de saída de um bloco a uma porta
de entrada de outro (ou a um `case` do próprio topo), compara:

- os literais que o produtor atribui à porta (`porta <= "0101"`);
- os valores que o consumidor decodifica nela (`when "0101"` dentro de
  `case porta is`, e `porta = "0101"` em condições).

Código emitido que um *bloco* consumidor não decodifica é problema: o
contrato do bloco define os códigos válidos, e o código cai no `when others`.
Quando o consumidor é o próprio topo, é só aviso: o topo integra e costuma
filtrar antes (na `luna6_prof_3`, o código do `LUI` nunca chega ao `case`
porque o topo testa a instrução antes; na `luna6_abl_m_reduzida_2`, a palavra
cai no `when others` de propósito). Valor decodificado que ninguém emite
também é só aviso (código morto). Nas 25 CPUs do repositório em 24/11/2026, a
regra acusa só a `luna6_abl_m_reduzida_4`.
Só olha literais de bits; constantes nomeadas e expressões ficam de fora.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["Ligacao", "checar_cpu", "texto_relatorio"]

_COMENTARIO = re.compile(r"--[^\n]*")
_INSTANCIA = re.compile(
    r"(\w+)\s*:\s*entity\s+work\.(\w+)\s*(?:generic\s+map\s*\(.*?\)\s*)?port\s+map\s*\((.*?)\)\s*;",
    re.I | re.S)
_ASSOC = re.compile(r"(\w+)\s*=>\s*([^,]+)")
_ENTIDADE = re.compile(r"entity\s+(\w+)\s+is\s+(?:generic\s*\(.*?\)\s*;\s*)?port\s*\((.*?)\)\s*;\s*end",
                       re.I | re.S)
_PORTA = re.compile(r"([\w\s,]+?)\s*:\s*(in|out|inout|buffer)\s+([^;]+)", re.I)
_BITS = r'"([01]+)"'


def _limpar(texto: str) -> str:
    return _COMENTARIO.sub("", texto)


def _portas(texto: str) -> dict[str, dict[str, str]]:
    """entidade -> {porta: direcao}"""
    out: dict[str, dict[str, str]] = {}
    for m in _ENTIDADE.finditer(texto):
        portas: dict[str, str] = {}
        for p in _PORTA.finditer(m.group(2) + ";"):
            for nome in p.group(1).split(","):
                if nome.strip():
                    portas[nome.strip().lower()] = p.group(2).lower()
        out[m.group(1).lower()] = portas
    return out


def _corpo(texto: str) -> str:
    m = re.search(r"\barchitecture\b.*", texto, re.I | re.S)
    return m.group(0) if m else texto


def emitidos(texto: str, sinal: str) -> set[str]:
    """Literais de bits atribuídos a `sinal` (`sinal <= "..."`)."""
    corpo = _corpo(_limpar(texto))
    return set(re.findall(rf"\b{re.escape(sinal)}\s*<=\s*{_BITS}", corpo, re.I))


def decodificados(texto: str, sinal: str) -> set[str]:
    """Valores de `sinal` que o código decodifica: escolhas do `case sinal is`
    (só no nível desse case, não nos aninhados) e comparações `sinal = "..."`."""
    corpo = _corpo(_limpar(texto))
    valores = set(re.findall(rf"\b{re.escape(sinal)}\s*=\s*{_BITS}", corpo, re.I))
    tokens = re.finditer(r"\bcase\s+(\w+)(?:\s*\([^)]*\))?\s+is\b|\bend\s+case\b|\bwhen\s+([^=]*?)=>",
                         corpo, re.I | re.S)
    pilha: list[str] = []
    for t in tokens:
        if t.group(1) is not None:
            pilha.append(t.group(1).lower())
        elif t.group(0).lower().startswith("end"):
            if pilha:
                pilha.pop()
        elif pilha and pilha[-1] == sinal.lower():
            valores |= set(re.findall(_BITS, t.group(2)))
    return valores


@dataclass
class Ligacao:
    sinal: str
    produtor: str            # "entidade.porta"
    consumidor: str          # "entidade.porta" ou "cpu (topo)"
    emitidos: set[str] = field(default_factory=set)
    decodificados: set[str] = field(default_factory=set)

    @property
    def sem_decodificacao(self) -> set[str]:
        return self.emitidos - self.decodificados if self.decodificados else set()

    @property
    def no_topo(self) -> bool:
        return self.consumidor.endswith("(topo)")

    @property
    def problema(self) -> bool:
        return bool(self.sem_decodificacao) and not self.no_topo

    @property
    def nunca_emitidos(self) -> set[str]:
        return self.decodificados - self.emitidos if self.emitidos else set()

    def como_dict(self) -> dict:
        return {"sinal": self.sinal, "produtor": self.produtor, "consumidor": self.consumidor,
                "emitidos": sorted(self.emitidos), "decodificados": sorted(self.decodificados),
                "sem_decodificacao": sorted(self.sem_decodificacao), "problema": self.problema,
                "nunca_emitidos": sorted(self.nunca_emitidos)}


def checar_cpu(pasta: Path, topo: str = "cpu") -> list[Ligacao]:
    """Ligações do topo entre um produtor e um consumidor que decodifica
    literais. Só devolve as que têm literais dos dois lados."""
    fontes = {f.stem.lower(): f.read_text(encoding="utf-8", errors="replace")
              for f in sorted((pasta / "src").glob("*.vhd"))}
    portas: dict[str, dict[str, str]] = {}
    texto_de: dict[str, str] = {}
    for texto in fontes.values():
        for ent, ps in _portas(_limpar(texto)).items():
            portas[ent] = ps
            texto_de[ent] = texto
    topo_txt = texto_de.get(topo)
    if topo_txt is None:
        return []

    # sinal do topo -> [(entidade, porta, direcao)]
    conexoes: dict[str, list[tuple[str, str, str]]] = {}
    for m in _INSTANCIA.finditer(_corpo(_limpar(topo_txt))):
        ent = m.group(2).lower()
        for a in _ASSOC.finditer(m.group(3)):
            formal, atual = a.group(1).lower(), a.group(2).strip().lower()
            if not re.fullmatch(r"\w+", atual):
                continue                     # fatia, expressão ou constante
            direcao = portas.get(ent, {}).get(formal, "")
            conexoes.setdefault(atual, []).append((ent, formal, direcao))

    ligacoes: list[Ligacao] = []
    for sinal, pontas in sorted(conexoes.items()):
        produtores = [(e, p) for e, p, d in pontas if d in ("out", "buffer")]
        consumidores = [(e, p) for e, p, d in pontas if d == "in"]
        for pe, pp in produtores:
            emit = emitidos(texto_de[pe], pp)
            if not emit:
                continue
            alvos = [(f"{ce}.{cp}", decodificados(texto_de[ce], cp)) for ce, cp in consumidores]
            alvos.append((f"{topo} (topo)", decodificados(topo_txt, sinal)))
            for nome, dec in alvos:
                if dec:
                    ligacoes.append(Ligacao(sinal, f"{pe}.{pp}", nome, emit, dec))
    return ligacoes


def problemas(ligacoes: list[Ligacao]) -> list[Ligacao]:
    return [l for l in ligacoes if l.problema]


def texto_relatorio(pasta: Path, ligacoes: list[Ligacao]) -> str:
    linhas = [f"{pasta.name}: {len(ligacoes)} ligacao(oes) com codigos dos dois lados, "
              f"{len(problemas(ligacoes))} com problema"]
    for l in ligacoes:
        estado = "PROBLEMA" if l.problema else "aviso" if l.sem_decodificacao else "ok"
        linhas.append(f"  {estado:<8} {l.sinal}: {l.produtor} -> {l.consumidor} "
                      f"({len(l.emitidos)} emitidos, {len(l.decodificados)} decodificados)")
        if l.sem_decodificacao:
            linhas.append(f"           emitidos e nao decodificados: {', '.join(sorted(l.sem_decodificacao))}")
        if l.nunca_emitidos:
            linhas.append(f"           aviso: decodificados e nunca emitidos: "
                          f"{', '.join(sorted(l.nunca_emitidos))}")
    return "\n".join(linhas) + "\n"


def como_json(pasta: Path, ligacoes: list[Ligacao]) -> str:
    return json.dumps({"cpu": pasta.name, "problemas": len(problemas(ligacoes)),
                       "ligacoes": [l.como_dict() for l in ligacoes]},
                      indent=2, ensure_ascii=False) + "\n"
