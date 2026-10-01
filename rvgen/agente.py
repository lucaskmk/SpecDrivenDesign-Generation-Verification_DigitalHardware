#!/usr/bin/env python3
"""O laco do agente: decompor, escrever, validar, corrigir, julgar.

REQ: FR-RV-47 (entrega completa: architecture.json, um VHDL por bloco,
cpu.toml), FR-RV-48 (laco de correcao com o diagnostico real, desfazendo o
que piorar), FR-RV-49 (veredito so do rvverify completo; escrita so em
src/; arquivos protegidos conferidos), FR-RV-50 (sessao auditavel).

Por que um agente de FASES FIXAS (ADR-018): um modelo local de 7 a 30
bilhoes de parametros se perde numa tarefa longa e aberta. Aqui ele nunca
escolhe o proximo passo nem recebe um shell. O orquestrador fixa a sequencia
e entrega ao modelo uma pergunta pequena por vez:

    1. decomposicao em blocos       -> JSON restrito por schema
    2. um arquivo por vez            -> um bloco ```vhdl
    3. cpu.toml                      -> sem modelo nenhum (rvgen.contrato)
    4. rvverify: compila?            -> 1 caso so, para o erro sair rapido
    5. rvverify: etapa RV32I         -> todos os casos da base
    6. rvverify: completo            -> as duas etapas (so para rv32im)
       ... em 4-6, cada falha vira: qual arquivo corrigir (erro do GHDL
       aponta sozinho; senao o modelo escolhe) -> arquivo novo -> medir de
       novo -> se piorou, desfaz
    7. veredito                      -> execucao completa, sem --casos

O modelo nunca ve o validador, nunca escreve fora de `<pasta>/src/` e nunca
decide se passou.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol

from . import contrato as ct
from .config import REPO_ROOT
from .executor import Execucao, Executor
from .llm import ErroLLM, Resposta, extrair_json, extrair_vhdl

__all__ = [
    "Agente",
    "ErroGeracao",
    "ErroIntegridade",
    "Placar",
    "Resultado",
    "placar_de",
    "validar_arquitetura",
    "arquivos_protegidos",
    "hash_de",
    "SCHEMA_ARQUITETURA",
]


class Cliente(Protocol):
    provedor: str
    modelo: str

    def conversar(self, mensagens: list[dict[str, str]], *,
                  schema: dict | None = None,
                  temperatura: float | None = None) -> Resposta: ...


class ErroGeracao(RuntimeError):
    """A geracao nao pode continuar (resposta inutilizavel, validador mudo...)."""


class ErroIntegridade(ErroGeracao):
    """Um arquivo do validador ou uma fonte fornecida mudou durante a geracao."""


_ARQUIVO_RE = re.compile(r"^src/[a-z][a-z0-9_]*\.vhd$")

# FR-RV-48: resposta identica ao arquivo atual -> o proximo pedido sai mais
# "quente", e fica assim enquanto as alteracoes nao melhorarem o placar. Com
# a temperatura padrao (0,2) o modelo local devolveu o mesmo cpu_top.vhd em
# 10 de 12 correcoes (TRV-9.8); com a escada 0,2 -> 0,6 -> 0,9, repetiu nas 3
# vezes a 0,6 e mudou nas 4 a 0,9 (TRV-9.12). None = a do cliente.
TEMPERATURAS_NA_REPETICAO: tuple[float | None, ...] = (None, 0.9)
_NOME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

SCHEMA_ARQUITETURA: dict = {
    "type": "object",
    "properties": {
        "blocks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "responsibility": {"type": "string"},
                    "ports": {"type": "array", "items": {"type": "string"}},
                    "satisfies": {"type": "array", "items": {"type": "string"}},
                    "design_rationale": {"type": "string"},
                },
                "required": ["name", "responsibility", "ports", "satisfies",
                             "design_rationale"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["blocks"],
}


def _schema_arquitetura(com_descricao: bool) -> dict:
    """Com descricao do usuario, a decomposicao tambem mapeia cada pedido
    para o bloco que o atende (FR-RV-52)."""
    if not com_descricao:
        return SCHEMA_ARQUITETURA
    schema = json.loads(json.dumps(SCHEMA_ARQUITETURA))
    schema["properties"]["requests"] = {
        "type": "array",
        "items": {"type": "object",
                  "properties": {"request": {"type": "string"},
                                 "blocks": {"type": "array", "items": {"type": "string"}},
                                 "how": {"type": "string"}},
                  "required": ["request", "blocks", "how"]},
    }
    schema["required"] = ["blocks", "requests"]
    return schema


def _pedidos(bruta: Any) -> list[dict]:
    """O mapeamento item da descricao -> bloco, so com texto (declaracao do modelo)."""
    if not isinstance(bruta, dict) or not isinstance(bruta.get("requests"), list):
        return []
    out = []
    for p in bruta["requests"]:
        if isinstance(p, dict) and str(p.get("request", "")).strip():
            out.append({"request": str(p["request"]).strip(),
                        "blocks": [str(b) for b in (p.get("blocks") or [])],
                        "how": str(p.get("how", "")).strip()})
    return out


def _schema_escolha(arquivos: list[str]) -> dict:
    return {"type": "object",
            "properties": {"file": {"type": "string", "enum": arquivos},
                           "reason": {"type": "string"}},
            "required": ["file", "reason"]}


# --------------------------------------------------------------------------
# pecas puras (testadas isoladamente)
# --------------------------------------------------------------------------

def validar_arquitetura(bruta: Any) -> tuple[list[dict] | None, str]:
    """Blocos normalizados, com o top por ultimo; ou None e o motivo.

    O nome do arquivo NUNCA vem do modelo: e sempre `src/<name>.vhd`.
    """
    if not isinstance(bruta, dict) or not isinstance(bruta.get("blocks"), list):
        return None, "a resposta nao tem a lista `blocks`"
    blocos: list[dict] = []
    vistos: set[str] = set()
    for b in bruta["blocks"]:
        if not isinstance(b, dict):
            return None, "um item de `blocks` nao e objeto"
        nome = str(b.get("name", "")).strip().lower()
        if not _NOME_RE.match(nome):
            return None, f"nome de bloco invalido: {nome!r}"
        if nome in ct.ENTIDADES_RESERVADAS:
            return None, f"{nome} ja e um arquivo fornecido"
        if nome in vistos:
            return None, f"bloco {nome} repetido"
        vistos.add(nome)
        blocos.append({
            "name": nome,
            "file": f"src/{nome}.vhd",
            "responsibility": str(b.get("responsibility", "")).strip(),
            "ports": [str(p) for p in (b.get("ports") or [])],
            "satisfies": [str(s) for s in (b.get("satisfies") or [])],
            "design_rationale": str(b.get("design_rationale", "")).strip(),
        })
    if not 2 <= len(blocos) <= 8:
        return None, f"{len(blocos)} blocos; o aceito e de 2 a 8"
    if ct.TOP not in vistos:
        return None, f"falta o bloco {ct.TOP}"
    if any(not b["responsibility"] for b in blocos):
        return None, "bloco sem `responsibility`"
    blocos = [b for b in blocos if b["name"] != ct.TOP] + \
             [b for b in blocos if b["name"] == ct.TOP]
    return blocos, ""


def arquivos_protegidos(raiz: Path = REPO_ROOT) -> list[Path]:
    """O validador inteiro e as fontes fornecidas que a entrega usa."""
    validador = [p for p in sorted((raiz / "rvverify").rglob("*.py"))
                 if "__pycache__" not in p.parts]
    return validador + [ct.FORNECIDOS_DIR / f for f in ct.FORNECIDOS]


def hash_de(arquivos: list[Path]) -> str:
    h = hashlib.sha256()
    for p in arquivos:
        h.update(p.as_posix().encode())
        h.update(p.read_bytes() if p.exists() else b"<ausente>")
    return h.hexdigest()


@dataclass(frozen=True)
class Placar:
    """O que uma execucao do rvverify mediu, reduzido ao que se compara."""

    compilou: bool
    passou: int
    total: int
    veredito: str | None

    def chave(self) -> tuple[bool, int]:
        return (self.compilou, self.passou)

    def texto(self) -> str:
        if not self.compilou:
            return "nao compilou"
        return f"{self.passou}/{self.total} casos"


def placar_de(ex: Execucao) -> Placar:
    rel = ex.relatorio or {}
    casos = [c for c in rel.get("casos", []) if isinstance(c, dict)]
    passou = sum(1 for c in casos if c.get("passed"))
    compilacao = (rel.get("compilacao") or {}).get("ok")
    compilou = compilacao is True or (compilacao is None and passou > 0)
    return Placar(compilou, passou, len(casos), rel.get("veredito"))


def _nome_base(caminho: str) -> str:
    return PurePosixPath(str(caminho).replace("\\", "/")).name


# `arquivo.vhd:12:5: mensagem` -- o formato das mensagens do GHDL com posicao
_GHDL_ERRO_RE = re.compile(
    r"^(?P<arquivo>[^\s:][^:]*\.vhdl?):(?P<linha>\d+):(?P<coluna>\d+):\s*(?P<mensagem>.*)$")


def erros_do_log(texto: str, limite: int = 20) -> list[dict]:
    """Mensagens do GHDL com posicao no fonte, lidas de um log.

    O `rvverify.builder` tem o equivalente, mas importa o cocotb; aqui o
    gerador precisa ler o log no host, onde o cocotb pode nao existir. As
    mensagens da biblioteca IEEE ficam de fora: nao apontam para o que o
    modelo escreveu.
    """
    out: list[dict] = []
    for bruta in texto.splitlines():
        m = _GHDL_ERRO_RE.match(bruta.strip())
        if not m or "ieee" in m["arquivo"].replace("\\", "/").lower().split("/")[0:-1] \
                or _nome_base(m["arquivo"]).startswith(("numeric_std", "std_logic_1164")):
            continue
        out.append({"arquivo": m["arquivo"], "linha": int(m["linha"]),
                    "coluna": int(m["coluna"]), "mensagem": m["mensagem"].strip()})
        if len(out) >= limite:
            break
    return out


def _caso_de_fumaca() -> str:
    """O primeiro caso da etapa RV32I no catalogo do proprio validador."""
    from rvverify.conformance import catalog
    return next(c["id"] for c in catalog() if c["etapa"] == "rv32i")


@dataclass(frozen=True)
class Resultado:
    veredito: str
    objetivo_atingido: bool
    placar: Placar
    iteracoes: int
    chamadas: int
    tokens_entrada: int
    tokens_saida: int
    segundos: float
    sessao: Path
    relatorio: Path


# --------------------------------------------------------------------------
# o agente
# --------------------------------------------------------------------------

class Agente:
    """Gera uma entrega em `pasta` e a leva ate o veredito do rvverify."""

    def __init__(self, *, cliente: Cliente, executor: Executor, pasta: Path,
                 tipo: ct.Tipo, isa: str, iteracoes: int = 12,
                 exemplo: Path | None = None, descricao: str | None = None,
                 forcar: bool = False,
                 relatar: Callable[[str], None] = print,
                 protegidos: Callable[[], str] | None = None,
                 caso_de_fumaca: Callable[[], str] = _caso_de_fumaca) -> None:
        self.cliente = cliente
        self.executor = executor
        self.pasta = Path(pasta).resolve()
        self.tipo = tipo
        self.isa = isa
        self.iteracoes = iteracoes
        self.exemplo = Path(exemplo).resolve() if exemplo else None
        self.descricao = (descricao or "").strip() or None
        self.forcar = forcar
        self.relatar = relatar
        self.protegidos = protegidos or (lambda: hash_de(arquivos_protegidos()))
        self.caso_de_fumaca = caso_de_fumaca
        self.nome = re.sub(r"[^a-z0-9_]", "_", self.pasta.name.lower()) or "cpu_gerada"
        self.contrato = ct.texto_do_contrato(tipo, isa)
        self.sessao = self.pasta / ".rvgen" / f"sessao-{datetime.now():%Y%m%d-%H%M%S}"
        self._chamadas = 0
        self._tokens = [0, 0]

    # -- utilitarios -------------------------------------------------------

    def _log(self, evento: dict) -> None:
        evento = {"t": datetime.now().isoformat(timespec="seconds"), **evento}
        with open(self.sessao / "sessao.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False) + "\n")

    def _destino(self, rel: str) -> Path:
        """FR-RV-49: o unico lugar em que o agente escreve e `<pasta>/src/`."""
        if not _ARQUIVO_RE.match(rel):
            raise ErroGeracao(f"escrita recusada: {rel!r} nao e src/<nome>.vhd")
        destino = (self.pasta / rel).resolve()
        if destino.parent != (self.pasta / "src").resolve():
            raise ErroGeracao(f"escrita recusada: {rel!r} sai de {self.pasta / 'src'}")
        return destino

    def _escrever(self, rel: str, conteudo: str) -> None:
        self._destino(rel).write_text(conteudo, encoding="utf-8")

    def _ler(self, rel: str) -> str:
        p = self._destino(rel)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _chamar(self, fase: str, alvo: str, mensagens: list[dict],
                schema: dict | None = None,
                temperatura: float | None = None) -> Resposta:
        """Uma chamada ao modelo, sempre registrada (FR-RV-50)."""
        self._chamadas += 1
        try:
            r = self.cliente.conversar(mensagens, schema=schema, temperatura=temperatura)
        except ErroLLM as e:
            self._log({"evento": "llm_erro", "fase": fase, "alvo": alvo, "erro": str(e)})
            raise
        self._tokens[0] += r.tokens_entrada or 0
        self._tokens[1] += r.tokens_saida or 0
        registradas = [{"role": m["role"], "content": "@contrato.txt"}
                       if m["role"] == "system" and m["content"] == self.contrato else m
                       for m in mensagens]
        self._log({"evento": "llm", "fase": fase, "alvo": alvo,
                   "provedor": r.provedor, "modelo": r.modelo,
                   "tokens_entrada": r.tokens_entrada, "tokens_saida": r.tokens_saida,
                   "segundos": r.segundos, "cortes": r.cortes,
                   "temperatura": temperatura,
                   "mensagens": registradas,
                   "resposta": r.texto})
        return r

    def _declaracoes(self, blocos: list[dict], exceto: str | None = None) -> str:
        partes = []
        for b in blocos:
            if b["file"] == exceto:
                continue
            decl = ct.declaracoes_de_entidade(self._ler(b["file"]))
            if decl:
                partes.append(f"-- {b['file']}\n{decl[0]}")
        return "\n\n".join(partes) or "(none yet)"

    def _texto_descricao(self) -> str:
        """FR-RV-52: o que o usuario pediu, sempre abaixo do contrato."""
        if not self.descricao:
            return ""
        return ("# Designer's description of the CPU (free text from the user)\n"
                f"{self.descricao}\n"
                "Follow this description wherever it does not conflict with the "
                "contract in the system message. Where it conflicts, the contract "
                "wins: it is what the validator checks.\n\n")

    def _texto_exemplo(self) -> str:
        if not self.exemplo:
            return ""
        partes = [f"-- {p.name}\n{p.read_text(encoding='utf-8')}"
                  for p in sorted((self.exemplo / "src").glob("*.vhd"))]
        return ("# Reference design (a DIFFERENT verified CPU from this project; "
                "adapt its ideas to this contract, do not copy names that the "
                "contract fixes differently)\n" + "\n\n".join(partes) + "\n\n")

    # -- fases ---------------------------------------------------------------

    def _preparar_pasta(self) -> None:
        if self.pasta.exists() and not self.forcar and \
                any(p.name != ".rvgen" for p in self.pasta.iterdir()):
            raise ErroGeracao(f"{self.pasta} ja tem conteudo; use --forcar para "
                              f"sobrescrever os arquivos gerados")
        (self.pasta / "src").mkdir(parents=True, exist_ok=True)
        (self.sessao / "rvverify").mkdir(parents=True, exist_ok=True)
        (self.sessao / "contrato.txt").write_text(self.contrato, encoding="utf-8")
        if self.descricao:
            (self.pasta / "descricao.md").write_text(
                "# Descricao da CPU pedida ao modelo\n\n"
                "Texto livre passado a `rvgen gerar` (FR-RV-52). NAO verificado pelo\n"
                "rvverify: o veredito julga so o contrato; o mapeamento destes pedidos\n"
                "para os blocos, em `architecture.json` (`requests`), e declaracao do\n"
                "modelo.\n\n" + self.descricao + "\n", encoding="utf-8")

    def _planejar(self) -> dict:
        padrao = ct.arquitetura_padrao(self.tipo, self.isa, self.nome)
        if self.descricao:
            padrao.update(descricao=self.descricao, requests=[],
                          requests_note="declared by the model; NOT verified by rvverify")
        sugestao = ", ".join(b["name"] for b in padrao["blocks"])
        pedidos = (
            "\nAlso answer `requests`: one entry per item of the designer's "
            "description, with the `blocks` that implement it and `how`; if the "
            "contract prevents an item, say so in `how` and leave `blocks` empty."
            if self.descricao else "")
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"{self._texto_exemplo()}{self._texto_descricao()}"
                f"Decompose this {self.tipo.nome} {self.isa.upper()} CPU into hardware "
                f"blocks. Answer ONLY with JSON: {{\"blocks\": [{{\"name\", "
                f"\"responsibility\", \"ports\", \"satisfies\", \"design_rationale\"}}], "
                f"\"notes\"}}.\nRules: 2 to 8 blocks; each block becomes "
                f"src/<name>.vhd with `entity <name>`; lowercase names; never "
                f"reuse a provided entity ({', '.join(sorted(ct.ENTIDADES_RESERVADAS))}); "
                f"the LAST block is `{ct.TOP}`, the top level that instantiates the "
                f"others and the provided memories; `ports` are VHDL port "
                f"declarations such as \"clk : in std_logic\"; `satisfies` lists "
                f"requirement IDs (FR-RV-xx); `design_rationale` justifies the "
                f"block by area, speed or verifiability. A sound decomposition "
                f"for this type is: {sugestao}.{pedidos}")},
        ]
        motivo = ""
        for tentativa in (1, 2):
            r = self._chamar("decomposicao", "architecture.json", mensagens,
                             schema=_schema_arquitetura(bool(self.descricao)))
            try:
                bruta = extrair_json(r.texto)
            except ErroLLM as e:
                bruta, motivo = None, str(e)
            blocos, motivo = validar_arquitetura(bruta) if bruta is not None else (None, motivo)
            if blocos:
                arq = dict(padrao, origem="modelo", blocks=blocos,
                           notes=str((bruta or {}).get("notes", "")))
                if self.descricao:
                    arq["requests"] = _pedidos(bruta)
                self.relatar(f"  decomposicao: {len(blocos)} blocos propostos pelo modelo"
                             + (f", {len(arq['requests'])} pedidos da descricao mapeados"
                                if self.descricao else ""))
                return arq
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                           f"That decomposition is invalid: {motivo}. Send the JSON again."}]
        self.relatar(f"  decomposicao do modelo invalida ({motivo}); usando a "
                     f"decomposicao padrao do tipo")
        self._log({"evento": "decomposicao_padrao", "motivo": motivo})
        return dict(padrao, notes=f"decomposicao padrao: a do modelo foi recusada ({motivo})")

    def _escrever_bloco(self, bloco: dict, arq: dict) -> None:
        plano = "\n".join(
            f"- {b['file']}: entity {b['name']} -- {b['responsibility']}\n"
            f"  ports: {'; '.join(b['ports']) or '(see contract)'}"
            for b in arq["blocks"])
        topo = (f"\nThis is the TOP LEVEL: follow the 'Top level' section of the "
                f"contract exactly (generics, ports, instance labels and signal "
                f"names) and instantiate every other block above."
                if bloco["name"] == ct.TOP else "")
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"{self._texto_exemplo()}{self._texto_descricao()}"
                f"Architecture of this CPU:\n{plano}\n\n"
                f"Entity declarations already written:\n"
                f"{self._declaracoes(arq['blocks'], exceto=bloco['file'])}\n\n"
                f"Write the complete file {bloco['file']} implementing entity "
                f"{bloco['name']}.\nResponsibility: {bloco['responsibility']}\n"
                f"Ports: {'; '.join(bloco['ports']) or '(see contract)'}{topo}")},
        ]
        self.relatar(f"  escrevendo {bloco['file']} ...")
        for tentativa in (1, 2):
            r = self._chamar("escrita", bloco["file"], mensagens)
            vhdl = extrair_vhdl(r.texto)
            if vhdl and re.search(rf"\bentity\s+{bloco['name']}\s+is\b", vhdl, re.IGNORECASE):
                self._escrever(bloco["file"], vhdl)
                self.relatar(f"  escrito  {bloco['file']} ({vhdl.count(chr(10))} linhas, "
                             f"{r.tokens_saida or '?'} tokens, {r.segundos} s)")
                return
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                           f"The answer has no ```vhdl block with `entity {bloco['name']} is`. "
                           f"Send the complete file {bloco['file']} again."}]
        raise ErroGeracao(f"o modelo nao produziu {bloco['file']} em 2 tentativas")

    def _validar(self, rotulo: str, etapa: str, casos: list[str] | None) -> Execucao:
        ex = self.executor.rodar(
            self.pasta, json_saida=self.sessao / "rvverify" / f"{rotulo}.json",
            workdir=self.sessao / "sim" / rotulo, build_root=self.sessao / "build",
            casos=casos, etapa=etapa)
        p = placar_de(ex)
        self._log({"evento": "rvverify", "rotulo": rotulo, "etapa": etapa,
                   "casos": casos, "comando": ex.comando, "codigo": ex.codigo,
                   "segundos": ex.segundos, "placar": p.texto(),
                   "veredito": p.veredito,
                   "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
        if ex.relatorio is None:
            raise ErroGeracao(
                f"o rvverify nao gerou relatorio (codigo {ex.codigo}); problema de "
                f"ambiente, nao da CPU:\n{ex.saida[-1500:]}")
        self.relatar(f"  rvverify {rotulo:<16} {p.texto():<16} ({ex.segundos} s)")
        return ex

    def _objetivo(self, etapa: str, ex: Execucao) -> bool:
        p = placar_de(ex)
        if etapa == "fumaca":
            return p.compilou
        if etapa == "rv32i":
            return p.compilou and p.total > 0 and p.passou == p.total
        return p.veredito == "aprovado"

    def _erros_dos_logs(self, ex: Execucao) -> list[dict]:
        """Erros do GHDL lidos do `build.log` que o rvverify deixou na sessao."""
        workdir = self.sessao / "sim" / ex.json_path.stem
        erros: list[dict] = []
        for log in sorted(workdir.rglob("build.log")):
            erros += erros_do_log(log.read_text(encoding="utf-8", errors="replace"))
        return erros

    def _linha_do_fonte(self, arquivo: str, linha: int) -> str:
        texto = self._ler(arquivo).splitlines()
        return texto[linha - 1].strip() if 0 < linha <= len(texto) else ""

    def _evidencia(self, ex: Execucao, arquivos: list[str]) -> tuple[str | None, str]:
        """(arquivo a corrigir, se o GHDL ja o apontou; evidencia em texto)."""
        from rvverify.feedback import resumo_em_texto

        rel = ex.relatorio or {}
        comp = rel.get("compilacao") or {}
        erros = comp.get("erros") or []
        nao_compilou = comp.get("ok") is False
        # Relatorio sem as linhas do GHDL (o rvverify ja perdeu esse erro uma
        # vez, TRV-9.8): sem elas o modelo corrige as cegas e devolve o mesmo
        # arquivo. O build.log da sessao continua tendo tudo.
        if not erros and comp.get("ok") is not True and \
                not any(c.get("passed") for c in rel.get("casos", [])):
            erros = self._erros_dos_logs(ex)
            nao_compilou = nao_compilou or bool(erros)
        if nao_compilou:
            por_nome = {PurePosixPath(a).name: a for a in arquivos}
            linhas = []
            for e in erros[:12]:
                nome = _nome_base(e.get("arquivo", "?"))
                linhas.append(f"{nome}:{e.get('linha')}:{e.get('coluna')}: {e.get('mensagem')}")
                if nome in por_nome:
                    fonte = self._linha_do_fonte(por_nome[nome], int(e.get("linha") or 0))
                    if fonte:
                        linhas.append(f"    {fonte}")
            alvo = next((por_nome[_nome_base(e.get("arquivo", ""))] for e in erros
                         if _nome_base(e.get("arquivo", "")) in por_nome), None)
            texto = "GHDL compilation failed:\n" + ("\n".join(linhas) or
                                                    str(comp.get("mensagem", ""))[:1500])
            return self._com_contrato(alvo, texto, arquivos)
        falhas = [c for c in rel.get("casos", []) if not c.get("passed")]
        blocos = []
        for c in falhas[:6]:
            diag = c.get("diagnostico")
            corpo = resumo_em_texto(diag) if diag else [str(c.get("detail", ""))[:400]]
            blocos.append(f"- case {c.get('id')} [{', '.join(c.get('requirements', []))}]\n"
                          + "\n".join(f"    {ln}" for ln in corpo))
        if len(falhas) > 6:
            blocos.append(f"... and {len(falhas) - 6} more failing cases")
        tipos = {(c.get("diagnostico") or {}).get("tipo") for c in falhas}
        # caminho de observacao inexistente: os nomes observados vivem no top
        alvo = f"src/{ct.TOP}.vhd" if tipos == {"observacao"} else None
        return self._com_contrato(alvo, "Failing test cases:\n" + "\n".join(blocos),
                                  arquivos)

    def _com_contrato(self, alvo: str | None, texto: str,
                      arquivos: list[str]) -> tuple[str | None, str]:
        """Acrescenta a checagem estatica do contrato a evidencia (FR-RV-48).

        Um erro do GHDL continua mandando no alvo: nada roda antes de compilar.
        Sem ele, a primeira divergencia do contrato aponta o arquivo.
        """
        avisos = ct.verificar_contrato(self.tipo, {a: self._ler(a) for a in arquivos})
        if not avisos:
            return alvo, texto
        texto += ("\n\nContract check (static inspection of the text; a suggestion):\n"
                  + "\n".join(f"- {a}: {m}" for a, m in avisos))
        return alvo or avisos[0][0], texto

    def _escolher(self, evidencia: str, arq: dict) -> str:
        arquivos = [b["file"] for b in arq["blocks"]]
        plano = "\n".join(f"- {b['file']}: {b['responsibility']}" for b in arq["blocks"])
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"The CPU was run by the validator.\n{evidencia}\n\nFiles:\n{plano}\n\n"
                f"Which ONE file most likely contains the bug? Answer ONLY with JSON "
                f"{{\"file\": one of {arquivos}, \"reason\": \"...\"}}.")},
        ]
        r = self._chamar("escolha", "-", mensagens, schema=_schema_escolha(arquivos))
        try:
            escolhido = str(extrair_json(r.texto).get("file", ""))
        except (ErroLLM, AttributeError):
            escolhido = ""
        return escolhido if escolhido in arquivos else f"src/{ct.TOP}.vhd"

    def _reescrever(self, alvo: str, evidencia: str, arq: dict,
                    nota: str | None, temperatura: float | None = None) -> str | None:
        nome = PurePosixPath(alvo).stem
        atual = self._ler(alvo)
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"{self._texto_descricao()}"
                f"The CPU was run by the validator and failed.\n{evidencia}\n\n"
                + (f"NOTE: {nota}\n\n" if nota else "")
                + f"Entity declarations of the other files (keep compatible):\n"
                f"{self._declaracoes(arq['blocks'], exceto=alvo)}\n\n"
                f"Current content of {alvo}:\n```vhdl\n{atual}```\n\n"
                f"Fix {alvo}. Keep the entity name and ports unless the evidence "
                f"shows that the ports themselves are wrong. Answer with the "
                f"complete corrected file in one ```vhdl block.")},
        ]
        for tentativa in (1, 2):
            r = self._chamar("correcao", alvo, mensagens, temperatura=temperatura)
            vhdl = extrair_vhdl(r.texto)
            if vhdl and re.search(rf"\bentity\s+{nome}\s+is\b", vhdl, re.IGNORECASE):
                return None if vhdl.strip() == atual.strip() else vhdl
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                           f"No ```vhdl block with `entity {nome} is`. Send the complete file."}]
        return None

    def _corrigir(self, arq: dict) -> tuple[Execucao, str, int]:
        """FR-RV-48: mede, corrige um arquivo, mede de novo; desfaz o que piora."""
        etapas = [("fumaca", "rv32i", [self.caso_de_fumaca()]), ("rv32i", "rv32i", None)]
        if self.isa == "rv32im":
            etapas.append(("completa", "ambas", None))
        arquivos = [b["file"] for b in arq["blocks"]]
        i = 0
        atual = self._validar(etapas[0][0], etapas[0][1], etapas[0][2])
        iteracao = 0
        nota: str | None = None
        repeticoes = 0          # respostas seguidas sem mudanca efetiva
        while True:
            nome_etapa, etapa, casos = etapas[i]
            if self._objetivo(nome_etapa, atual):
                if i + 1 == len(etapas):
                    return atual, nome_etapa, iteracao
                i += 1
                nome_etapa, etapa, casos = etapas[i]
                atual = self._validar(nome_etapa, etapa, casos)
                continue
            if iteracao >= self.iteracoes:
                self.relatar(f"  orcamento de {self.iteracoes} iteracoes esgotado")
                return atual, nome_etapa, iteracao
            iteracao += 1
            alvo, evidencia = self._evidencia(atual, arquivos)
            motivo = "apontado pelo GHDL/diagnostico" if alvo else "escolhido pelo modelo"
            alvo = alvo or self._escolher(evidencia, arq)
            temperatura = TEMPERATURAS_NA_REPETICAO[
                min(repeticoes, len(TEMPERATURAS_NA_REPETICAO) - 1)]
            extra = f", temperatura {temperatura}" if temperatura is not None else ""
            self.relatar(f"  iteracao {iteracao}/{self.iteracoes}: corrigindo {alvo} "
                         f"({motivo}{extra})")
            antes = self._ler(alvo)
            novo = self._reescrever(alvo, evidencia, arq, nota, temperatura)
            if novo is None:
                repeticoes += 1
                nota = (f"Your last answer for {alvo} was unusable or identical to the "
                        f"current file. Make a real change.")
                self._log({"evento": "correcao_vazia", "alvo": alvo, "iteracao": iteracao,
                           "temperatura": temperatura})
                continue
            self._escrever(alvo, novo)
            depois = self._validar(f"it{iteracao:02d}-{nome_etapa}", etapa, casos)
            if placar_de(depois).chave() < placar_de(atual).chave():
                self._escrever(alvo, antes)
                nota = (f"Your previous change to {alvo} made the result worse "
                        f"({placar_de(depois).texto()} instead of "
                        f"{placar_de(atual).texto()}) and was reverted. Try a different fix.")
                self.relatar(f"  piorou ({placar_de(depois).texto()}); alteracao desfeita")
                self._log({"evento": "reversao", "alvo": alvo, "iteracao": iteracao,
                           "antes": placar_de(atual).texto(),
                           "depois": placar_de(depois).texto()})
            else:
                # so uma MELHORA devolve a temperatura normal; mudar sem
                # melhorar ainda e estar travado (TRV-9.12)
                if placar_de(depois).chave() > placar_de(atual).chave():
                    repeticoes = 0
                atual, nota = depois, None

    # -- ponta a ponta -----------------------------------------------------

    def gerar(self) -> Resultado:
        inicio = time.monotonic()
        self._preparar_pasta()
        selo = self.protegidos()
        self._log({"evento": "inicio", "pasta": str(self.pasta), "tipo": self.tipo.nome,
                   "isa": self.isa, "provedor": self.cliente.provedor,
                   "modelo": self.cliente.modelo, "executor": self.executor.nome,
                   "iteracoes": self.iteracoes,
                   "exemplo": str(self.exemplo) if self.exemplo else None,
                   "descricao": self.descricao})

        arq = self._planejar()
        (self.pasta / "architecture.json").write_text(
            json.dumps(arq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        for bloco in arq["blocks"]:
            self._escrever_bloco(bloco, arq)
        arquivos = [b["file"] for b in arq["blocks"]]
        (self.pasta / "cpu.toml").write_text(
            ct.renderizar_cpu_toml(self.nome, self.pasta, self.tipo, self.isa, arquivos),
            encoding="utf-8")
        self.relatar("  cpu.toml gerado a partir do contrato (sem modelo)")

        ultima, etapa, iteracoes = self._corrigir(arq)

        # FR-RV-49: nada que o julga pode ter mudado enquanto a CPU era gerada
        if self.protegidos() != selo:
            self._log({"evento": "integridade", "ok": False})
            raise ErroIntegridade(
                "um arquivo de rvverify/ ou uma fonte fornecida mudou durante a "
                "geracao; o veredito foi recusado")
        # o veredito vem de uma execucao COMPLETA (as duas etapas, sem --casos)
        final = ultima if etapa == "completa" else self._validar("final", "ambas", None)
        p = placar_de(final)
        rel = final.relatorio or {}
        base = (rel.get("por_etapa") or {}).get("rv32i") or {}
        if self.isa == "rv32im":
            atingido = p.veredito == "aprovado"
        else:
            atingido = p.veredito in ("aprovado", "incompleto") and \
                base.get("falhou") == 0 and bool(base.get("total"))
        resultado = Resultado(
            veredito=p.veredito or "desconhecido", objetivo_atingido=atingido,
            placar=p, iteracoes=iteracoes, chamadas=self._chamadas,
            tokens_entrada=self._tokens[0], tokens_saida=self._tokens[1],
            segundos=round(time.monotonic() - inicio, 1), sessao=self.sessao,
            relatorio=final.json_path)
        resumo = {"veredito": resultado.veredito, "objetivo_atingido": atingido,
                  "placar": p.texto(), "iteracoes": iteracoes,
                  "chamadas": resultado.chamadas,
                  "tokens_entrada": resultado.tokens_entrada,
                  "tokens_saida": resultado.tokens_saida,
                  "segundos": resultado.segundos,
                  "provedor": self.cliente.provedor, "modelo": self.cliente.modelo,
                  "tipo": self.tipo.nome, "isa": self.isa,
                  "exemplo": str(self.exemplo) if self.exemplo else None,
                  "descricao": self.descricao,
                  "relatorio": final.json_path.relative_to(self.pasta).as_posix()}
        (self.sessao / "resultado.json").write_text(
            json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._log({"evento": "fim", **resumo})
        return resultado
