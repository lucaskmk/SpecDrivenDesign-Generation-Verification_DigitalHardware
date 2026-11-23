#!/usr/bin/env python3
"""Rastreabilidade por rótulos (adaptação do VCLM do UCAgent).

Os rótulos não são inventados pela IA: vêm de `specs/rotulos.md`, um catálogo
versionado `FG-*` (grupo funcional) → `FC-*` (função) → `CK-*` (ponto de
checagem). Com `rvgen gerar --rotulos`:

- o contrato de cada bloco lista na seção `## Labels` os `CK-*` pelos quais o
  bloco responde;
- cada teste cocotb cita, num comentário `# CK: ...`, os `CK-*` que verifica;
- este módulo confere nos dois sentidos, sem IA: rótulo citado que não existe
  no catálogo (ou não está no contrato do bloco) é recusado; rótulo do
  contrato sem teste aprovado, ou do catálogo sem bloco responsável, é
  omissão e entra na métrica de cobertura.

Isto substitui a ideia antiga de `-- REQ: FR-RV-xx`, removida porque os IDs
não existiam em lugar nenhum: aqui todo rótulo vem de um arquivo e é checado.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

__all__ = ["Catalogo", "ErroRotulos", "carregar", "citados", "ck_do_contrato",
           "ck_do_teste", "secao_labels", "sem_secao_labels", "problemas_contrato",
           "problemas_teste", "cobertura"]

ARQUIVO = "rotulos.md"
ROTULO_RE = re.compile(r"\b(?:FG|FC|CK)-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
CK_RE = re.compile(r"\bCK-[A-Z0-9]+(?:-[A-Z0-9]+)*\b")
_FG_RE = re.compile(r"^##\s+(FG-[A-Z0-9-]+)\b(.*)$")
_FC_RE = re.compile(r"^###\s+(FC-[A-Z0-9-]+)\b")
_CK_RE_LINHA = re.compile(r"^-\s+(CK-[A-Z0-9-]+)\s*:\s*(.+)$")
_LABELS_RE = re.compile(r"(?ms)^## Labels[ \t]*\n(.*?)(?=^##\s|\Z)")
_COMENTARIO_CK_RE = re.compile(r"(?m)^\s*#\s*CK\s*:\s*(.+)$")


class ErroRotulos(ValueError):
    """Catálogo de rótulos ausente ou malformado."""


@dataclass(frozen=True)
class Ponto:
    ck: str
    fc: str
    fg: str
    descricao: str
    so_rv32m: bool


@dataclass(frozen=True)
class Catalogo:
    pontos: tuple[Ponto, ...]

    def ativos(self, isa: str) -> tuple[Ponto, ...]:
        return tuple(p for p in self.pontos if isa == "rv32im" or not p.so_rv32m)

    def cks(self, isa: str) -> set[str]:
        return {p.ck for p in self.ativos(isa)}

    def todos(self) -> set[str]:
        """Todo rótulo FG/FC/CK do catálogo, de qualquer ISA."""
        return {p.ck for p in self.pontos} | {p.fc for p in self.pontos} | \
               {p.fg for p in self.pontos}

    def texto_para_prompt(self, isa: str) -> str:
        linhas, fg, fc = [], None, None
        for p in self.ativos(isa):
            if p.fg != fg:
                linhas.append(p.fg)
                fg = p.fg
            if p.fc != fc:
                linhas.append(f"  {p.fc}")
                fc = p.fc
            linhas.append(f"    {p.ck}: {p.descricao}")
        return "\n".join(linhas)


def carregar(arquivo: Path) -> Catalogo:
    try:
        texto = arquivo.read_text(encoding="utf-8")
    except OSError as e:
        raise ErroRotulos(f"catalogo de rotulos {arquivo} nao pode ser lido: {e}") from e
    pontos: list[Ponto] = []
    fg = fc = None
    so_m = False
    vistos: set[str] = set()
    for n, linha in enumerate(texto.splitlines(), 1):
        if m := _FG_RE.match(linha):
            fg, fc, so_m = m.group(1), None, "[RV32M]" in m.group(2)
        elif m := _FC_RE.match(linha):
            if fg is None:
                raise ErroRotulos(f"{arquivo}:{n}: {m.group(1)} fora de um FG")
            fc = m.group(1)
        elif m := _CK_RE_LINHA.match(linha.strip()):
            if fc is None:
                raise ErroRotulos(f"{arquivo}:{n}: {m.group(1)} fora de um FC")
            if m.group(1) in vistos:
                raise ErroRotulos(f"{arquivo}:{n}: {m.group(1)} repetido")
            vistos.add(m.group(1))
            pontos.append(Ponto(m.group(1), fc, fg, m.group(2).strip(), so_m))
    if not pontos:
        raise ErroRotulos(f"{arquivo} nao define nenhum CK-*")
    return Catalogo(tuple(pontos))


def citados(texto: str) -> set[str]:
    return set(ROTULO_RE.findall(texto or ""))


def secao_labels(contrato: str) -> str | None:
    m = _LABELS_RE.search(contrato or "")
    return m.group(1) if m else None


def sem_secao_labels(contrato: str) -> str:
    """O contrato sem a seção `## Labels` (ela é guardada à parte)."""
    return _LABELS_RE.sub("", contrato or "").rstrip() + "\n"


def ck_do_contrato(contrato: str) -> set[str]:
    secao = secao_labels(contrato)
    return set(CK_RE.findall(secao)) if secao is not None else set()


def ck_do_teste(codigo: str) -> set[str]:
    """CKs declarados nos comentários `# CK: ...` de um módulo cocotb."""
    out: set[str] = set()
    for m in _COMENTARIO_CK_RE.finditer(codigo or ""):
        out |= set(CK_RE.findall(m.group(1)))
    return out


def problemas_contrato(contrato: str, catalogo: Catalogo, isa: str) -> list[str]:
    """Motivos para recusar a seção `## Labels` de um contrato (vazio = ok)."""
    secao = secao_labels(contrato)
    if secao is None:
        return ["missing `## Labels` section"]
    validos = catalogo.cks(isa)
    citados_secao = citados(secao)
    inventados = sorted(r for r in citados_secao if r.startswith("CK-") and r not in validos)
    erros = []
    if inventados:
        erros.append("labels not in the catalog (do not invent labels): " + ", ".join(inventados))
    if not set(CK_RE.findall(secao)) & validos:
        erros.append("`## Labels` must list at least one CK-* label from the catalog")
    return erros


def problemas_teste(codigo: str, cks_do_bloco: set[str], catalogo: Catalogo, isa: str,
                    *, obrigatorio: bool = True) -> list[str]:
    """Motivos para recusar os rótulos de um teste (vazio = ok)."""
    declarados = ck_do_teste(codigo)
    if not declarados:
        return ["missing `# CK: ...` comment naming the CK labels this test verifies"] \
            if obrigatorio else []
    validos = catalogo.cks(isa)
    erros = []
    inventados = sorted(declarados - validos)
    if inventados:
        erros.append("CK labels not in the catalog: " + ", ".join(inventados))
    fora = sorted((declarados & validos) - cks_do_bloco)
    if fora:
        erros.append("CK labels not listed in this component's `## Labels`: " + ", ".join(fora))
    return erros


def _ler(caminho: Path) -> str:
    try:
        return caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def cobertura(sessao: Path, blocos: list[str], catalogo: Catalogo, isa: str) -> dict:
    """Cobertura de rótulos por bloco e da CPU, só com arquivos da sessão.

    Por bloco: CKs do contrato com pelo menos um teste aprovado que os cita
    (testbench principal e casos públicos aprovados). CPU: CKs do catálogo
    (na ISA) cobertos por algum bloco; `sem_dono` são CKs que nenhum contrato
    assumiu."""
    validos = catalogo.cks(isa)
    por_bloco: dict[str, dict] = {}
    cobertos_cpu: set[str] = set()
    assumidos: set[str] = set()
    for nome in blocos:
        contrato = _ler(sessao / "component_specs" / f"{nome}.comp_spec.txt")
        cks = ck_do_contrato(contrato) & validos
        assumidos |= cks
        testes = [sessao / "testes" / f"test_{nome}.py",
                  *sorted((sessao / "testes_casos" / nome / "publicos").glob("*.py"))]
        citados_testes: set[str] = set()
        for t in testes:
            citados_testes |= ck_do_teste(_ler(t))
        cobertos = cks & citados_testes
        cobertos_cpu |= cobertos
        por_bloco[nome] = {"contrato": sorted(cks), "cobertos": sorted(cobertos),
                           "sem_teste": sorted(cks - cobertos),
                           "cobertura": round(len(cobertos) / len(cks), 3) if cks else None}
    return {"isa": isa, "catalogo": len(validos), "por_bloco": por_bloco,
            "cobertos": sorted(cobertos_cpu), "sem_dono": sorted(validos - assumidos),
            "sem_teste": sorted(validos - cobertos_cpu),
            "cobertura_cpu": round(len(cobertos_cpu) / len(validos), 3) if validos else None}


def gravar_cobertura(sessao: Path, blocos: list[str], catalogo: Catalogo, isa: str) -> dict:
    dados = cobertura(sessao, blocos, catalogo, isa)
    (sessao / "rotulos_cobertura.json").write_text(
        json.dumps(dados, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return dados
