#!/usr/bin/env python3
"""Experimentos lado a lado: `python -m rvgen comparar`.

REQ: FR-RV-51 (tabela de experimentos), FR-RV-50 (os numeros vem dos
registros da sessao), NFR-RV-02 (nada re-medido nem inferido; custo rotulado
como estimativa).

Uma geracao (`rvgen gerar`) deixa em `<pasta>/.rvgen/sessao-*/` o
`resultado.json` e o relatorio final do `rvverify`. Este modulo so LE esses
arquivos e os poe lado a lado -- nao roda modelo, nao roda GHDL. O unico
numero que nao estava registrado e o custo, e por isso ele sai sempre como
estimativa: tokens registrados x preco publico do provedor no dia da
comparacao (o OpenRouter pode dar desconto de cache, entao e um teto). Modelo
local custa zero em dinheiro.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from .config import REPO_ROOT
from .executor import ler_relatorio

__all__ = [
    "Linha",
    "sessoes",
    "provedor_de",
    "linha_de",
    "precos_openrouter",
    "tabela_texto",
    "tabela_markdown",
    "PASTA_PADRAO",
]

PASTA_PADRAO = REPO_ROOT / "experimentos"
URL_MODELOS = "https://openrouter.ai/api/v1/models"

Precos = dict[str, tuple[float, float]]      # id -> (US$/token entrada, US$/token saida)


@dataclass(frozen=True)
class Linha:
    experimento: str
    sessao: str
    modelo: str
    provedor: str
    tipo: str
    isa: str
    veredito: str
    rv32i: str
    rv32im: str
    iteracoes: int
    chamadas: int
    tokens_entrada: int
    tokens_saida: int
    minutos: float
    custo: str
    custo_usd: float | None
    exemplo: bool
    descricao: bool = False


# --------------------------------------------------------------------------
# onde estao as sessoes
# --------------------------------------------------------------------------

def _pastas_de_experimento(alvo: Path) -> list[Path]:
    """`alvo` e um experimento (tem .rvgen) ou uma pasta de experimentos."""
    if (alvo / ".rvgen").is_dir():
        return [alvo]
    if not alvo.is_dir():
        return []
    return sorted(p for p in alvo.iterdir() if (p / ".rvgen").is_dir())


def sessoes(alvos: list[Path], *, todas: bool = False) -> list[Path]:
    """Diretorios de sessao com `resultado.json`: a mais recente de cada
    experimento, ou todas. Sessoes que pararam com erro nao tem resultado e
    ficam de fora -- nao ha veredito para comparar."""
    out: list[Path] = []
    for alvo in alvos:
        for pasta in _pastas_de_experimento(alvo):
            achadas = sorted(p.parent for p in (pasta / ".rvgen").glob("sessao-*/resultado.json"))
            out += achadas if todas else achadas[-1:]
    return out


# --------------------------------------------------------------------------
# uma linha
# --------------------------------------------------------------------------

def provedor_de(sessao: Path) -> str:
    try:
        return str(json.loads((sessao / "resultado.json").read_text(encoding="utf-8"))
                   .get("provedor", ""))
    except (OSError, ValueError):
        return ""


def _etapa(relatorio: dict | None, etapa: str, placar: str) -> str:
    if placar == "nao compilou":
        return "nao compilou"
    if not relatorio:
        return "-"
    dados = (relatorio.get("por_etapa") or {}).get(etapa)
    if dados:
        return f"{dados.get('passou', 0)}/{dados.get('total', 0)}"
    return "pulada" if relatorio.get("pulado") else "-"


def _custo(provedor: str, modelo: str, entrada: int, saida: int,
           precos: Precos | None) -> tuple[str, float | None]:
    if provedor == "ollama":
        return "0 (local)", 0.0
    if precos is None:
        return "?", None
    preco = precos.get(modelo)
    if preco is None:       # o provedor pode devolver o nome com sufixo de versao
        candidatos = [m for m in precos if modelo.startswith(m)]
        preco = precos[max(candidatos, key=len)] if candidatos else None
    if preco is None:
        return "?", None
    valor = entrada * preco[0] + saida * preco[1]
    return f"~US$ {valor:.4f}", valor


def linha_de(sessao: Path, precos: Precos | None) -> Linha:
    r = json.loads((sessao / "resultado.json").read_text(encoding="utf-8"))
    pasta = sessao.parent.parent
    relatorio = ler_relatorio(pasta / r["relatorio"]) if r.get("relatorio") else None
    placar = str(r.get("placar", ""))
    entrada, saida = int(r.get("tokens_entrada") or 0), int(r.get("tokens_saida") or 0)
    custo, valor = _custo(r.get("provedor", ""), r.get("modelo", ""), entrada, saida, precos)
    return Linha(
        experimento=pasta.name,
        sessao=sessao.name.removeprefix("sessao-"),
        modelo=r.get("modelo", "?"),
        provedor=r.get("provedor", "?"),
        tipo=r.get("tipo", "?"),
        isa=r.get("isa", "?"),
        veredito=str(r.get("veredito", "?")).upper(),
        rv32i=_etapa(relatorio, "rv32i", placar),
        rv32im=_etapa(relatorio, "rv32m", placar) if r.get("isa") == "rv32im" else "-",
        iteracoes=int(r.get("iteracoes") or 0),
        chamadas=int(r.get("chamadas") or 0),
        tokens_entrada=entrada,
        tokens_saida=saida,
        minutos=round(float(r.get("segundos") or 0) / 60, 1),
        custo=custo,
        custo_usd=valor,
        exemplo=bool(r.get("exemplo")),
        descricao=bool(r.get("descricao")),
    )


def precos_openrouter(timeout: float = 15.0, url: str = URL_MODELOS) -> Precos | None:
    """Precos publicos por token do catalogo do OpenRouter (nao exige chave)."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            dados = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None
    precos: Precos = {}
    for m in dados.get("data", []):
        p = m.get("pricing") or {}
        try:
            precos[m["id"]] = (float(p.get("prompt", 0)), float(p.get("completion", 0)))
        except (KeyError, TypeError, ValueError):
            continue
    return precos or None


# --------------------------------------------------------------------------
# saida
# --------------------------------------------------------------------------

COLUNAS = ("experimento", "modelo", "tipo", "ISA", "veredito", "RV32I", "RV32IM",
           "iteracoes", "chamadas", "tokens (entrada+saida)", "tempo", "custo")


def _celulas(l: Linha) -> list[str]:
    modelo = f"{l.modelo} ({'local' if l.provedor == 'ollama' else l.provedor})"
    if l.exemplo:
        modelo += " +exemplo"
    if l.descricao:        # FR-RV-52: descrita e nao descrita nao se comparam de igual
        modelo += " +descricao"
    return [l.experimento, modelo, l.tipo, l.isa, l.veredito, l.rv32i, l.rv32im,
            str(l.iteracoes), str(l.chamadas), f"{l.tokens_entrada}+{l.tokens_saida}",
            f"{l.minutos} min", l.custo]


def _nota(linhas: list[Linha], precos_ok: bool) -> str:
    fonte_placar = "Veredito e placar: relatorio final do rvverify de cada sessao."
    if all(l.provedor == "ollama" for l in linhas):
        return f"custo: modelos locais, sem custo em dinheiro (0). {fonte_placar}"
    fonte = (f"preco publico do OpenRouter em {date.today():%Y-%m-%d}" if precos_ok
             else "preco do OpenRouter indisponivel (sem rede ou --sem-rede)")
    return (f"custo: ESTIMATIVA = tokens registrados x {fonte}; modelo local = 0. "
            f"{fonte_placar}")


def tabela_texto(linhas: list[Linha], precos_ok: bool) -> str:
    grade = [list(COLUNAS)] + [_celulas(l) for l in linhas]
    larguras = [max(len(linha[i]) for linha in grade) for i in range(len(COLUNAS))]
    texto = ["  ".join(c.ljust(w) for c, w in zip(linha, larguras)).rstrip()
             for linha in grade]
    texto.insert(1, "  ".join("-" * w for w in larguras))
    return "\n".join(texto) + "\n\n" + _nota(linhas, precos_ok) + "\n"


def tabela_markdown(linhas: list[Linha], precos_ok: bool) -> str:
    cab = "| " + " | ".join(COLUNAS) + " |"
    sep = "|" + "|".join("---" for _ in COLUNAS) + "|"
    corpo = ["| " + " | ".join(c.replace("|", "\\|") for c in _celulas(l)) + " |"
             for l in linhas]
    return "\n".join([f"# Comparacao de experimentos ({date.today():%Y-%m-%d})", "",
                      cab, sep, *corpo, "", _nota(linhas, precos_ok), ""])
