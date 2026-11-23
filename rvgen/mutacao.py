#!/usr/bin/env python3
"""Qualidade dos testes gerados por mutação: `python -m rvgen mutacao`.

Pergunta: os testes de componente que a IA escreveu pegam erros reais no
VHDL? Para responder sem IA, o módulo cria mutantes de um bloco de uma CPU
aprovada (uma mudança pequena por mutante: operador, constante, condição,
bit de seleção) e roda, em cada mutante, três níveis de teste:

1. `bloco`: os testes de componente do próprio bloco (o testbench e os casos
   públicos aprovados que a IA escreveu, os mesmos que a evolução roda na
   linha de base);
2. `cpu`: os testes de componente do topo `cpu` (integração, também da IA);
3. `juiz`: o `spec-riscv-test` com os programas `riscv-tests` (sem IA).

Um mutante é *morto* num nível quando algum teste daquele nível falha.
Mutante que nem compila é *natimorto* e sai da conta. Mutante que nenhum
nível mata pode ser *equivalente* (não muda o comportamento visível, como
trocar `unsigned` por `signed` nos 32 bits baixos de um produto) e precisa
ser conferido à mão. Mutation score de um nível = mortos / viáveis.

Precisa de GHDL, cocotb e do `spec-riscv-test` (a imagem `rvgen-veredito`).
A geração dos mutantes (`gerar_mutantes`) é Python puro e testável sem eles.
"""

from __future__ import annotations

import json
import re
import shutil
import tomllib
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable

__all__ = ["Mutante", "gerar_mutantes", "testes_do_bloco", "rodar", "resumo_texto",
           "resumo_markdown"]


@dataclass(frozen=True)
class Mutante:
    id: str
    operador: str        # relacional, aritmetico, logico, constante, selecao, tipo
    linha: int           # 1-based
    original: str        # trecho original
    mutado: str          # trecho que entrou no lugar
    texto: str = field(repr=False, compare=False)   # arquivo VHDL inteiro do mutante


# --------------------------------------------------------------------------
# geracao de mutantes (Python puro)
# --------------------------------------------------------------------------

def _mascarar(linha: str) -> str:
    """A linha com comentário e literais de caractere/cadeia trocados por
    espaços de mesmo tamanho: os operadores só são procurados no código."""
    out = list(linha)
    i = 0
    while i < len(linha):
        c = linha[i]
        if linha.startswith("--", i):
            for j in range(i, len(linha)):
                out[j] = " "
            break
        if c == '"':
            fim = linha.find('"', i + 1)
            fim = len(linha) - 1 if fim < 0 else fim
            for j in range(i, fim + 1):
                out[j] = " "
            i = fim + 1
            continue
        if c == "'" and i + 2 < len(linha) and linha[i + 2] == "'":
            out[i:i + 3] = "   "
            i += 3
            continue
        i += 1
    return "".join(out)


# (operador, regex no código mascarado, substituições)
_TROCAS: list[tuple[str, re.Pattern, Callable[[str], list[str]]]] = [
    # `=` e `/=` só em condição: `<=`, `>=`, `:=` e `=>` ficam de fora
    ("relacional", re.compile(r"(?<![<>/:=])=(?![=>])"), lambda s: ["/="]),
    ("relacional", re.compile(r"/="), lambda s: ["="]),
    ("relacional", re.compile(r"(?<![<=/-])<(?![=>])"), lambda s: [">"]),
    ("relacional", re.compile(r"(?<![=-])>(?![=])"), lambda s: ["<"]),
    ("aritmetico", re.compile(r"(?<![eE\d])\+"), lambda s: ["-"]),
    ("aritmetico", re.compile(r"(?<![-eE\d])-(?![-])"), lambda s: ["+"]),
    ("aritmetico", re.compile(r"(?<![/-])/(?![=])"), lambda s: [" rem "]),
    ("aritmetico", re.compile(r"\brem\b", re.I), lambda s: ["/", "mod"]),
    ("aritmetico", re.compile(r"\bmod\b", re.I), lambda s: ["rem"]),
    ("logico", re.compile(r"\band\b", re.I), lambda s: ["or"]),
    ("logico", re.compile(r"\bor\b", re.I), lambda s: ["and"]),
    ("logico", re.compile(r"\bxor\b", re.I), lambda s: ["or"]),
    ("tipo", re.compile(r"\bunsigned\(", re.I), lambda s: ["signed("]),
    ("tipo", re.compile(r"(?<!un)\bsigned\(", re.I), lambda s: ["unsigned("]),
]

_SLICE_RE = re.compile(r"\((\d+)\s+downto\s+(\d+)\)", re.I)
_HEX_RE = re.compile(r'[xX]"([0-9A-Fa-f_]+)"')
_BIT_RE = re.compile(r"'([01])'")
_PORTAS_RE = re.compile(r"\b(port|generic)\s*\(", re.I)
_DECLARACOES = ("library ", "use ", "entity ", "end ", "architecture ", "signal ",
                "variable ", "constant ", "type ", "subtype ", "component ", "alias ")


def _inicio_comentario(linha: str) -> int:
    """Índice do `--` que abre comentário (fora de cadeias), ou len(linha)."""
    mascara = _mascarar(linha)
    for i, (orig, masc) in enumerate(zip(linha, mascara)):
        if linha.startswith("--", i) and masc == " " and orig == "-":
            # `_mascarar` apaga tudo a partir do comentário; uma cadeia apagada
            # começa com aspas, não com `--`
            if all(c == " " for c in mascara[i:]):
                return i
    return len(linha)


def _sem_mutacao(linhas: list[str]) -> set[int]:
    """Índices de linhas que não se mutam: bibliotecas, entidade, listas de
    portas/generics (inclusive `port map`) e declarações de sinal/variável
    (mudar a largura de uma declaração é erro de compilação, não de
    comportamento)."""
    fora: set[int] = set()
    profundidade = 0
    for i, linha in enumerate(linhas):
        mascara = _mascarar(linha)
        baixa = mascara.strip().lower()
        if profundidade > 0:
            fora.add(i)
            profundidade += mascara.count("(") - mascara.count(")")
            continue
        m = _PORTAS_RE.search(mascara)
        if m:
            fora.add(i)
            profundidade = mascara[m.end() - 1:].count("(") - mascara[m.end() - 1:].count(")")
            continue
        if not baixa or baixa.startswith(_DECLARACOES):
            fora.add(i)
    return fora


def gerar_mutantes(texto: str, prefixo: str = "m") -> list[Mutante]:
    """Mutantes de primeira ordem de um arquivo VHDL, em ordem determinística."""
    linhas = texto.splitlines(keepends=True)
    fora = _sem_mutacao(linhas)
    achados: list[tuple[str, int, int, int, str, str]] = []   # op, linha, ini, fim, orig, novo

    for i, linha in enumerate(linhas):
        if i in fora:
            continue
        mascara = _mascarar(linha)
        for operador, regex, novos in _TROCAS:
            for m in regex.finditer(mascara):
                original = linha[m.start():m.end()]
                for novo in novos(original):
                    achados.append((operador, i, m.start(), m.end(), original, novo))
        for m in _SLICE_RE.finditer(mascara):
            alto, baixo = int(m.group(1)), int(m.group(2))
            original = linha[m.start():m.end()]
            for d in (-1, 1):
                if baixo + d >= 0:
                    achados.append(("selecao", i, m.start(), m.end(), original,
                                    f"({alto + d} downto {baixo + d})"))
        # constantes: os literais estão mascarados, então se procura na linha
        comentario = _inicio_comentario(linha)
        for m in _HEX_RE.finditer(linha):
            if m.start() >= comentario:
                continue
            digitos = m.group(1).replace("_", "")
            largura = len(digitos) * 4
            valor = int(digitos, 16)
            for bit in sorted({0, largura - 1}):
                novo = valor ^ (1 << bit)
                achados.append(("constante", i, m.start(), m.end(), m.group(0),
                                f'x"{novo:0{len(digitos)}X}"'))
        for m in _BIT_RE.finditer(linha):
            if m.start() >= comentario:
                continue
            achados.append(("constante", i, m.start(), m.end(), m.group(0),
                            "'1'" if m.group(1) == "0" else "'0'"))

    achados.sort(key=lambda a: (a[1], a[2], a[0], a[5]))
    mutantes = []
    for n, (operador, i, ini, fim, original, novo) in enumerate(achados, 1):
        nova = linhas[i][:ini] + novo + linhas[i][fim:]
        corpo = "".join(linhas[:i] + [nova] + linhas[i + 1:])
        mutantes.append(Mutante(id=f"{prefixo}{n:03d}", operador=operador, linha=i + 1,
                                original=original, mutado=novo, texto=corpo))
    return mutantes


# --------------------------------------------------------------------------
# testes de uma CPU aprovada
# --------------------------------------------------------------------------

def sessao_aprovada(cpu: Path) -> Path:
    """A sessão mais recente com `resultado.json` aprovado."""
    for s in sorted((cpu / ".rvgen").glob("sessao-*/resultado.json"), reverse=True):
        try:
            if json.loads(s.read_text(encoding="utf-8")).get("veredito") == "aprovado":
                return s.parent
        except ValueError:
            continue
    raise ValueError(f"{cpu} não tem sessão aprovada")


def testes_do_bloco(sessao: Path, bloco: str) -> list[Path]:
    """Testbench principal, casos públicos aprovados e regressões do bloco
    (o mesmo conjunto que `rvgen.evolucao._testes_do_bloco` roda)."""
    testes = [sessao / "testes" / f"test_{bloco}.py",
              *sorted((sessao / "testes_casos" / bloco / "publicos").glob("*.py")),
              *sorted((sessao / "regressoes").glob(f"test_{bloco}*.py"))]
    return [t for t in testes if t.is_file()]


def fontes_da_cpu(cpu: Path) -> list[str]:
    """Fontes na ordem de compilação: `cpu.toml` ou `architecture.json`."""
    toml = cpu / "cpu.toml"
    if toml.is_file():
        return list(tomllib.loads(toml.read_text(encoding="utf-8"))["design"]["sources"])
    arq = json.loads((cpu / "architecture.json").read_text(encoding="utf-8"))
    return [b["file"] for b in arq["blocks"]]


# --------------------------------------------------------------------------
# execucao (GHDL + cocotb + spec-riscv-test)
# --------------------------------------------------------------------------

@dataclass
class Resultado:
    id: str
    operador: str
    linha: int
    original: str
    mutado: str
    compila: bool = True
    bloco: bool | None = None      # True = morto pelos testes do bloco
    cpu: bool | None = None        # True = morto pelos testes do topo cpu
    juiz: bool | None = None       # True = morto pelo spec-riscv-test
    juiz_placar: str = ""
    detalhe: str = ""


def _copiar_cpu(cpu: Path, destino: Path, fontes: list[str]) -> None:
    if destino.exists():
        shutil.rmtree(destino)
    (destino / "src").mkdir(parents=True)
    for rel in fontes:
        shutil.copyfile(cpu / rel, destino / rel)
    for nome in ("cpu.toml", "architecture.json"):
        if (cpu / nome).is_file():
            shutil.copyfile(cpu / nome, destino / nome)


def _morto_por(executor, pasta: Path, componente: str, testes: list[Path],
               fontes: list[Path], trabalho: Path) -> tuple[bool | None, bool, str]:
    """(morto?, compilou?, detalhe). Para no primeiro teste que falha."""
    for teste in testes:
        rot = f"{componente}-{teste.stem}"
        ex = executor.rodar_componente(
            pasta, componente=componente, teste=teste,
            json_saida=trabalho / "res" / f"{rot}.json",
            workdir=trabalho / "sim" / rot, build_root=trabalho / "build" / componente,
            fontes=fontes, timeout=600)
        rel = ex.relatorio or {}
        if not (rel.get("compilacao") or {}).get("ok"):
            return None, False, f"{teste.name}: nao compilou"
        if not rel.get("passed"):
            return True, True, f"{teste.name}: {rel.get('detail', '')}"[:200]
    return False, True, ""


def _placar(relatorio: dict | None) -> tuple[int, int]:
    rel = relatorio or {}
    return int(rel.get("passed") or 0), int(rel.get("executed") or 0)


def rodar(cpu: Path, bloco: str, *, isa: str, trabalho: Path, executor,
          juiz_testes: list[str] | None = None, paralelo: int = 2,
          limite: int | None = None, relatar: Callable[[str], None] = print) -> dict:
    """Gera e roda os mutantes de `bloco`; devolve o resumo (também gravado
    em `<trabalho>/resultado.json`)."""
    cpu = cpu.resolve()
    sessao = sessao_aprovada(cpu)
    fontes = fontes_da_cpu(cpu)
    arquivo = next(f for f in fontes if Path(f).stem == bloco)
    mutantes = gerar_mutantes((cpu / arquivo).read_text(encoding="utf-8"))
    if limite:
        mutantes = mutantes[:limite]
    testes_bloco = testes_do_bloco(sessao, bloco)
    testes_cpu = testes_do_bloco(sessao, "cpu") if bloco != "cpu" else []
    relatar(f"{cpu.name}/{bloco}: {len(mutantes)} mutantes; {len(testes_bloco)} testes do bloco, "
            f"{len(testes_cpu)} do cpu; juiz {isa}"
            + (f" ({','.join(juiz_testes)})" if juiz_testes else ""))

    # controle: a CPU original precisa passar em tudo, senão a medida não vale
    original = Mutante("original", "-", 0, "", "", (cpu / arquivo).read_text(encoding="utf-8"))

    def um(m: Mutante) -> Resultado:
        r = Resultado(m.id, m.operador, m.linha, m.original, m.mutado)
        pasta = trabalho / m.id / "cpu"
        _copiar_cpu(cpu, pasta, fontes)
        (pasta / arquivo).write_text(m.texto, encoding="utf-8")
        srcs = [pasta / f for f in fontes]
        r.bloco, r.compila, det = _morto_por(executor, pasta, bloco, testes_bloco, srcs,
                                             trabalho / m.id)
        if not r.compila:
            r.detalhe = det
            return r
        r.detalhe = det
        if testes_cpu:
            r.cpu, _, det_cpu = _morto_por(executor, pasta, "cpu", testes_cpu, srcs,
                                           trabalho / m.id)
            r.detalhe = r.detalhe or det_cpu
        ex = executor.rodar(pasta, json_saida=trabalho / m.id / "juiz" / "report.json",
                            workdir=trabalho / m.id / "juiz", build_root=trabalho / m.id / "juiz",
                            casos=juiz_testes, etapa=isa, timeout=1800)
        passou, total = _placar(ex.relatorio)
        r.juiz_placar = f"{passou}/{total}" if total else "sem relatorio"
        r.juiz = not (total > 0 and passou == total)
        return r

    controle = um(original)
    if not controle.compila or controle.bloco or controle.cpu or controle.juiz:
        raise RuntimeError(f"a CPU original não passa nos próprios testes: {controle}")
    relatar(f"  controle: original passa em tudo (juiz {controle.juiz_placar})")

    resultados: list[Resultado] = []
    with ThreadPoolExecutor(max_workers=max(1, paralelo)) as pool:
        for r in pool.map(um, mutantes):
            resultados.append(r)
            estado = ("natimorto" if not r.compila else
                      " ".join(f"{n}={'X' if v else '.'}" for n, v in
                               (("bloco", r.bloco), ("cpu", r.cpu), ("juiz", r.juiz))
                               if v is not None))
            relatar(f"  {r.id} l.{r.linha} {r.operador:<10} {r.original!r} -> {r.mutado!r}: {estado}")

    resumo = _resumir(cpu, bloco, isa, juiz_testes, testes_bloco, testes_cpu, resultados)
    trabalho.mkdir(parents=True, exist_ok=True)
    (trabalho / "resultado.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
    return resumo


def _resumir(cpu: Path, bloco: str, isa: str, juiz_testes, testes_bloco, testes_cpu,
             resultados: list[Resultado]) -> dict:
    viaveis = [r for r in resultados if r.compila]

    def score(campo: str) -> dict:
        mortos = sum(1 for r in viaveis if getattr(r, campo))
        return {"mortos": mortos, "viaveis": len(viaveis),
                "score": round(mortos / len(viaveis), 3) if viaveis else None}

    componentes = sum(1 for r in viaveis if r.bloco or r.cpu)
    return {
        "cpu": cpu.name, "bloco": bloco, "isa": isa, "juiz_testes": juiz_testes,
        "data": datetime.now().strftime("%Y-%m-%d"),
        "testes_bloco": [t.name for t in testes_bloco],
        "testes_cpu": [t.name for t in testes_cpu],
        "mutantes": len(resultados), "natimortos": len(resultados) - len(viaveis),
        "por_nivel": {"bloco": score("bloco"), "cpu": score("cpu"), "juiz": score("juiz")},
        "componentes_bloco_ou_cpu": {"mortos": componentes, "viaveis": len(viaveis)},
        "so_o_juiz_matou": [r.id for r in viaveis if r.juiz and not (r.bloco or r.cpu)],
        "so_componentes_mataram": [r.id for r in viaveis if (r.bloco or r.cpu) and not r.juiz],
        "sobreviventes": [r.id for r in viaveis if not (r.bloco or r.cpu or r.juiz)],
        "resultados": [asdict(r) for r in resultados],
    }


# --------------------------------------------------------------------------
# saida
# --------------------------------------------------------------------------

def _pct(d: dict) -> str:
    return "-" if d.get("score") is None else f"{d['mortos']}/{d['viaveis']} ({100 * d['score']:.0f}%)"


def resumo_texto(r: dict) -> str:
    n = r["por_nivel"]
    return "\n".join([
        f"{r['cpu']}/{r['bloco']}: {r['mutantes']} mutantes, {r['natimortos']} natimortos",
        f"  testes do bloco ({len(r['testes_bloco'])}): {_pct(n['bloco'])}",
        f"  testes do cpu ({len(r['testes_cpu'])}):   {_pct(n['cpu'])}",
        f"  juiz spec-riscv-test:  {_pct(n['juiz'])}",
        f"  so o juiz matou: {len(r['so_o_juiz_matou'])}; so componentes mataram: "
        f"{len(r['so_componentes_mataram'])}; sobreviventes (talvez equivalentes): "
        f"{len(r['sobreviventes'])} {r['sobreviventes']}",
    ]) + "\n"


def resumo_markdown(resumos: list[dict]) -> str:
    linhas = ["| CPU | Bloco | Mutantes viáveis | Testes do bloco | Testes do `cpu` | Juiz | Só o juiz matou | Sobreviventes |",
              "|---|---|---|---|---|---|---|---|"]
    for r in resumos:
        n = r["por_nivel"]
        linhas.append(f"| `{r['cpu']}` | `{r['bloco']}` | {n['juiz']['viaveis']} | {_pct(n['bloco'])} | "
                      f"{_pct(n['cpu'])} | {_pct(n['juiz'])} | {len(r['so_o_juiz_matou'])} | "
                      f"{len(r['sobreviventes'])} |")
    return "\n".join(linhas) + "\n"
