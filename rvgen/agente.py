#!/usr/bin/env python3
"""O laco do agente: decompor, escrever, validar, corrigir, julgar.

REQ: FR-RV-47 (entrega completa: architecture.json, um VHDL por bloco),
FR-RV-48 (laco de correcao com o diagnostico real, desfazendo o
que piorar), FR-RV-49 (veredito só do spec-riscv-test completo; escrita só em
src/; arquivos protegidos conferidos), FR-RV-50 (sessao auditavel).

Por que um agente de fases fixas: um modelo local de 7 a 30
bilhoes de parametros se perde numa tarefa longa e aberta. Aqui ele nunca
escolhe o proximo passo nem recebe um shell. O orquestrador fixa a sequencia
e entrega ao modelo uma pergunta pequena por vez:

    1. inventario de instrucoes      -> JSON restrito por schema
    2. decomposicao em blocos        -> JSON restrito por schema
    3. um arquivo por vez            -> um bloco ```vhdl
    4. spec-riscv-test: fumaca       -> um programa oficial
    5. spec-riscv-test: suite        -> todos os programas oficiais do perfil
       ... em 4-6, cada falha vira: qual arquivo corrigir (erro do GHDL
       aponta sozinho; senao o modelo escolhe) -> arquivo novo -> medir de
       novo -> se piorou, desfaz
     6. veredito                      -> execução completa, sem --tests

O modelo nunca ve o validador, nunca escreve fora de `<pasta>/src/` e nunca
decide se passou.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import shutil
import threading
import time
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Protocol

from . import contrato as ct
from .config import REPO_ROOT
from .executor import Execucao, Executor
from .llm import ErroLLM, Resposta, extrair_json, extrair_python, extrair_vhdl
from .riscv_asm import ErroAssemblyRV32I, validar_assembly_riscv
from .vcd import resumir as resumir_vcd

__all__ = [
    "Agente",
    "ErroGeracao",
    "ErroIntegridade",
    "Placar",
    "Resultado",
    "placar_de",
    "componentes_nao_integrados",
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


class ErroPlanoTeste(ErroGeracao):
    """Candidato de expansão inválido; exige replanejamento, não VHDL."""


_ARQUIVO_RE = re.compile(r"^src/[a-z][a-z0-9_]*\.vhd$")
_INSTANCIA_ENTITY_WORK_RE = re.compile(
    r"(?im)^\s*(?P<label>[a-zA-Z]\w*)\s*:\s*entity\s+work\.(?P<entity>[a-zA-Z]\w*)\b"
    r"(?:\s*\([^)]*\))?\s*(?:generic\s+map\s*\(.*?\)\s*)?port\s+map\s*\(")

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
                    "depends_on": {"type": "array", "items": {"type": "string"}},
                    "design_rationale": {"type": "string"},
                },
                "required": ["name", "responsibility", "ports", "design_rationale"],
            },
        },
        "notes": {"type": "string"},
    },
    "required": ["blocks"],
}

SCHEMA_INSTRUCOES: dict = {
    "type": "object",
    "properties": {"instructions": {"type": "array", "items": {
        "type": "object", "properties": {"mnemonic": {"type": "string"},
        "description": {"type": "string"}}, "required": ["mnemonic", "description"]}}},
    "required": ["instructions"],
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
                           "reason": {"type": "string"},
                           "lines": {"type": "array", "minItems": 1,
                                     "items": {"type": "integer", "minimum": 1}}},
            "required": ["file", "reason", "lines"]}


def _schema_hipotese_exploratoria(arquivos: list[str], ancora_oficial: dict | None = None) -> dict:
    schema = {"type": "object",
            "properties": {
                "file": {"type": "string", "enum": arquivos},
                "hypothesis": {"type": "string"},
                "evidence": {"type": "array", "minItems": 1,
                             "items": {"type": "string"}},
                "test_plan": {"type": "string"},
                "failure_meaning": {"type": "string"},
                "pass_meaning": {"type": "string"},
            },
            "required": ["file", "hypothesis", "evidence", "test_plan",
                         "failure_meaning", "pass_meaning"]}
    if ancora_oficial:
        schema["properties"]["official_anchor"] = {"type": "object"}
    return schema


_SCHEMA_REVISAO_HIPOTESE = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["confirmed", "refuted", "inconclusive"]},
        "rationale": {"type": "string"},
        "evidence": {"type": "array", "minItems": 2, "items": {"type": "string"}},
        "diagnostic_test_valid": {"type": "boolean"},
        "normative_approval_allowed": {"type": "boolean"},
    },
    "required": ["verdict", "rationale", "evidence", "diagnostic_test_valid",
                 "normative_approval_allowed"],
}


def _schema_diagnostico_interno(caminhos: list[str]) -> dict:
    """Plano de uma única observação VPI, escolhido pelo orquestrador."""
    return {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "hypothesis": {"type": "string"},
            "observation_paths": {"type": "array", "minItems": 1,
                                  "items": {"type": "string", "enum": caminhos}},
            "test_plan": {"type": "string"},
            "failure_meaning": {"type": "string"},
        },
        "required": ["id", "hypothesis", "observation_paths", "test_plan", "failure_meaning"],
    }


_SCHEMA_TRIAGEM_COMPONENTE = {
    "type": "object",
    "properties": {
        "causa": {"type": "string", "enum": ["vhdl", "testbench", "spec", "ambigua"]},
        "evidencias": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["causa", "evidencias"],
}

_SCHEMA_PROBES_INTERNOS = {
    "type": "object",
    "properties": {
        "probes": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {"signal": {"type": "string"},
                               "purpose": {"type": "string"}},
                "required": ["signal", "purpose"],
            },
        },
    },
    "required": ["probes"],
}

_SCHEMA_PLANO_EXPANSAO = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["add", "complete"]},
        "remaining": {"type": "integer", "minimum": 0},
        "coverage_gap": {"type": "string"},
        "behavior": {"type": "string"},
        "prerequisites": {"type": "array", "items": {"type": "string"}},
        "new_factor": {"type": "string"},
        "stimulus": {"type": "string"},
        "support_witness_path": {"type": "string"},
        "public_observations": {"type": "array", "items": {"type": "string"}},
        "forbidden": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["decision", "remaining"],
}

_SCHEMA_LOTE_EXPANSAO = {
    "type": "object",
        "properties": {
            "decision": {"type": "string", "enum": ["add_batch", "complete"]},
        "cases": {"type": "array", "items": _SCHEMA_PLANO_EXPANSAO},
    },
    "required": ["decision", "cases"],
}


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
            "depends_on": [str(d).strip().lower() for d in (b.get("depends_on") or [])],
        })
    if not 2 <= len(blocos) <= 8:
        return None, f"{len(blocos)} blocos; o aceito e de 2 a 8"
    if ct.TOP not in vistos:
        return None, f"falta o bloco {ct.TOP}"
    if any(not b["responsibility"] for b in blocos):
        return None, "bloco sem `responsibility`"
    por_nome = {b["name"]: b for b in blocos}
    for b in blocos:
        # A omissao preserva compatibilidade com planos anteriores: os blocos
        # folha nao dependem de gerados e o topo depende de todos os demais.
        if not b["depends_on"] and b["name"] == ct.TOP:
            b["depends_on"] = [n for n in vistos if n != ct.TOP]
        if len(set(b["depends_on"])) != len(b["depends_on"]):
            return None, f"dependencia repetida em {b['name']}"
        for dep in b["depends_on"]:
            if dep not in por_nome:
                return None, f"{b['name']} depende de bloco inexistente {dep!r}"
            if dep == b["name"]:
                return None, f"{b['name']} depende de si mesmo"

    # Ordem topologica deterministica, mantendo a ordem proposta entre blocos
    # independentes. O topo continua obrigatoriamente por ultimo.
    ordenados: list[dict] = []
    pendentes = list(blocos)
    while pendentes:
        prontos = [b for b in pendentes
                   if all(d in {x["name"] for x in ordenados} for d in b["depends_on"])]
        if not prontos:
            return None, "as dependencias entre blocos formam um ciclo"
        for b in prontos:
            if b["name"] != ct.TOP:
                ordenados.append(b)
        pendentes = [b for b in pendentes if b not in prontos]
        for b in prontos:
            if b["name"] == ct.TOP:
                # topo so entra quando nenhuma outra entidade gerada resta
                if pendentes:
                    pendentes.append(b)
                else:
                    ordenados.append(b)
    return ordenados, ""


def validar_instrucoes(bruta: Any, isa: str) -> tuple[list[dict] | None, str]:
    """Valida uma explicação curta para cada mnemônico da ISA escolhida."""
    if not isinstance(bruta, dict) or not isinstance(bruta.get("instructions"), list):
        return None, "a resposta nao tem a lista `instructions`"
    esperadas = ct.instrucoes_da_isa(isa)
    por_nome: dict[str, dict] = {}
    for item in bruta["instructions"]:
        if not isinstance(item, dict):
            return None, "um item de `instructions` nao e objeto"
        nome = str(item.get("mnemonic", "")).lower().strip()
        descricao = str(item.get("description", "")).strip()
        if not nome or not descricao or nome in por_nome:
            return None, "cada instrucao precisa de mnemonic unico e description"
        por_nome[nome] = {"mnemonic": nome, "description": descricao}
    if set(por_nome) != set(esperadas):
        return None, "instructions nao correspondem exatamente a ISA"
    return [por_nome[nome] for nome in esperadas], ""


def arquivos_protegidos(raiz: Path = REPO_ROOT) -> list[Path]:
    """O validador inteiro e as fontes fornecidas que a entrega usa."""
    base_validador = raiz / "spec-riscv-test"
    validador = [p for p in sorted(base_validador.rglob("*"))
                  if p.is_file() and "__pycache__" not in p.parts and
                  not any(parte.startswith("out") or parte == ".venv" for parte in p.parts)]
    return validador + [ct.FORNECIDOS_DIR / f for f in ct.FORNECIDOS]


def hash_de(arquivos: list[Path]) -> str:
    h = hashlib.sha256()
    for p in arquivos:
        h.update(p.as_posix().encode())
        h.update(p.read_bytes() if p.exists() else b"<ausente>")
    return h.hexdigest()


@dataclass(frozen=True)
class Placar:
    """O que uma execução de ``spec-riscv-test`` mediu."""

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
    if "status" in rel:
        total = int(rel.get("executed", 0) or 0)
        passou = int(rel.get("passed", 0) or 0)
        compilou = rel.get("status") == "passed" or total > 0
        veredito = "aprovado" if rel.get("status") == "passed" else "reprovado"
        return Placar(compilou, passou, total, veredito)
    casos = [c for c in rel.get("casos", []) if isinstance(c, dict)]
    passou = sum(1 for c in casos if c.get("passed"))
    compilacao = (rel.get("compilacao") or {}).get("ok")
    compilou = compilacao is True or (compilacao is None and passou > 0)
    return Placar(compilou, passou, len(casos), rel.get("veredito"))


def _nome_base(caminho: str) -> str:
    return PurePosixPath(str(caminho).replace("\\", "/")).name


def componentes_nao_integrados(vhdl_top: str, blocos: list[dict]) -> list[str]:
    """Blocos planejados que o top não instancia diretamente via ``entity work``.

    A regra é deliberadamente verificável por texto: o top precisa declarar uma
    instância VHDL explícita com ``port map`` para cada bloco gerado. Isso não
    tenta provar a semântica completa do fio a fio; impede, porém, que uma CPU
    reimplemente silenciosamente componentes que foram gerados e aprovados.
    """
    instanciados = {m["entity"].lower() for m in _INSTANCIA_ENTITY_WORK_RE.finditer(vhdl_top)}
    return [b["name"] for b in blocos if b["name"] != ct.TOP and
            b["name"].lower() not in instanciados]


# `arquivo.vhd:12:5: mensagem` -- o formato das mensagens do GHDL com posicao
_GHDL_ERRO_RE = re.compile(
    r"^(?P<arquivo>[^\s:][^:]*\.vhdl?):(?P<linha>\d+):(?P<coluna>\d+):\s*(?P<mensagem>.*)$")


def erros_do_log(texto: str, limite: int = 20) -> list[dict]:
    """Mensagens do GHDL com posicao no fonte, lidas de um log.

    O wrapper oficial tem o equivalente, mas importa o cocotb; aqui o
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


_COCOTB_INICIO_TESTE_RE = re.compile(
    r"\brunning\s+(?P<nome>test_[A-Za-z0-9_.]+)(?:\s+\(\d+/\d+\))?")
_COCOTB_EXPECTED_GOT_RE = re.compile(
    r"\b(?P<sinal>[A-Za-z_]\w*) expected (?P<esperado>0x[0-9a-fA-F]+),\s*"
    r"got (?P<observado>0x[0-9a-fA-F]+)")


def _entradas_literais_por_teste(fonte: str) -> dict[str, str]:
    """Portas do DUT dirigidas por literais, agrupadas por teste Cocotb.

    Isto nao tenta interpretar Python arbitrario: serve apenas para expor no
    diagnostico os vetores diretos que a propria suite aplicou ao DUT.
    """
    try:
        arvore = ast.parse(fonte)
    except SyntaxError:
        return {}
    saida: dict[str, str] = {}
    for no in ast.walk(arvore):
        if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) or not no.name.startswith("test_"):
            continue
        entradas: list[str] = []
        for atribuicao in ast.walk(no):
            if not isinstance(atribuicao, (ast.Assign, ast.AnnAssign)):
                continue
            alvos = atribuicao.targets if isinstance(atribuicao, ast.Assign) else [atribuicao.target]
            for alvo in alvos:
                if not (isinstance(alvo, ast.Attribute) and alvo.attr == "value" and
                        isinstance(alvo.value, ast.Attribute) and
                        isinstance(alvo.value.value, ast.Name) and alvo.value.value.id == "dut"):
                    continue
                try:
                    valor = ast.literal_eval(atribuicao.value)
                except (ValueError, TypeError):
                    continue
                if isinstance(valor, int):
                    entradas.append(f"{alvo.value.attr}=0x{valor:X}")
        if entradas:
            saida[no.name] = ", ".join(entradas[:6])
    return saida


def tabela_falhas_cocotb(diagnostico: str, fonte_teste: str) -> str:
    """Tabela determinística de todas as falhas Cocotb presentes no log.

    A LLM recebe a tabela como evidência factual, junto do contrato normativo.
    Assim, uma falha destacada pela triagem não oculta as demais falhas da mesma
    execução. Retorna texto vazio quando o log não possui a estrutura Cocotb.
    """
    inicios = list(_COCOTB_INICIO_TESTE_RE.finditer(diagnostico))
    entradas = _entradas_literais_por_teste(fonte_teste)
    linhas: list[str] = []
    for indice, inicio in enumerate(inicios):
        fim = inicios[indice + 1].start() if indice + 1 < len(inicios) else len(diagnostico)
        trecho = diagnostico[inicio.start():fim]
        qualificado = inicio["nome"]
        nome = qualificado.rsplit(".", 1)[-1]
        if not re.search(rf"\b{re.escape(qualificado)}\s+failed\b", trecho, re.IGNORECASE):
            continue
        aplicado = entradas.get(nome, "não extraível estaticamente")
        if achado := _COCOTB_EXPECTED_GOT_RE.search(trecho):
            esperado = "0x" + achado["esperado"][2:].upper()
            observado = "0x" + achado["observado"][2:].upper()
            resultado = (f"{achado['sinal']}: esperado {esperado}, "
                         f"observado {observado}")
        else:
            erro = next((linha.strip() for linha in trecho.splitlines()
                         if "Error" in linha or "Exception" in linha), "falha sem assertion parseável")
            resultado = erro.replace("|", "\\|")
        linhas.append(f"| `{nome}` | `{aplicado}` | {resultado} |")
    if not linhas:
        return ""
    return ("Falhas observadas nesta execução (corrija todas as linhas, não apenas uma):\n\n"
            "| Teste | Entradas literais dirigidas | Assertion/erro observado |\n"
            "|---|---|---|\n" + "\n".join(linhas))


def _falha_de_assertion(ex: Execucao) -> bool:
    """Há simulação executada e uma assertion Cocotb reprovada, não erro de build."""
    rel = ex.relatorio or {}
    if not (rel.get("compilacao") or {}).get("ok"):
        return False
    texto = str(rel.get("diagnostico") or ex.saida)
    # A linha-fonte de um traceback pode conter ``assert ...`` embora a
    # exceção efetiva seja AttributeError/ValueError (por exemplo, probe VPI
    # inexistente dentro da expressão). Só a exceção final do traceback
    # classifica uma falha como evidência sobre o DUT.
    excecoes = re.findall(
        r"(?m)^\s*(?:[A-Za-z_]\w*\.)?([A-Za-z_]\w*(?:Error|Exception))\s*(?::|$)",
        texto)
    return bool(excecoes and excecoes[-1] == "AssertionError")


def _caso_de_fumaca() -> str:
    """Caso oficial mínimo para verificar compilação e execução integrada."""
    return "simple"


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
    """Gera uma entrega em `pasta` e a leva ao veredito oficial."""

    def __init__(self, *, cliente: Cliente, executor: Executor, pasta: Path,
                    microarquitetura: str, isa: str, iteracoes: int = 12,
                    tentativas_revisao_semantica: int = 3,
                    max_casos_teste: int = 32,
                   max_casos_internos: int = 8,
                    parallel_testes: int = 1,
                  exemplo: Path | None = None, descricao: str | None = None,
                  forcar: bool = False, testes_componentes: bool = False,
                  testes_internos: bool = False,
                  regressoes_componentes: bool = False,
                  gates_componentes: bool = False,
                 sessao_existente: Path | None = None,
                 relatar: Callable[[str], None] = print,
                 protegidos: Callable[[], str] | None = None,
                 caso_de_fumaca: Callable[[], str] = _caso_de_fumaca) -> None:
        self.cliente = cliente
        self.executor = executor
        self.pasta = Path(pasta).resolve()
        self.microarquitetura = microarquitetura
        self.isa = isa
        self.iteracoes = iteracoes
        self.tentativas_revisao_semantica = max(1, tentativas_revisao_semantica)
        self.max_casos_teste = max_casos_teste
        self.max_casos_internos = max(1, max_casos_internos)
        self.parallel_testes = max(1, parallel_testes)
        self.exemplo = Path(exemplo).resolve() if exemplo else None
        self.descricao = (descricao or "").strip() or None
        self.forcar = forcar
        self.testes_componentes = testes_componentes
        self.testes_internos = testes_internos
        self.regressoes_componentes = regressoes_componentes
        self.gates_componentes = gates_componentes
        self._relatar_bruto = relatar
        self._escopos_log: list[dict[str, str]] = []
        self.protegidos = protegidos or (lambda: hash_de(arquivos_protegidos()))
        self.caso_de_fumaca = caso_de_fumaca
        self.nome = re.sub(r"[^a-z0-9_]", "_", self.pasta.name.lower()) or "cpu_gerada"
        self.contrato = ct.texto_do_contrato(microarquitetura, isa)
        self.contrato_testes = self.contrato + "\n\n# Cocotb Testbench Rules\n" + ct.texto_de_testes()
        self.sessao = (Path(sessao_existente).resolve() if sessao_existente else
                       self.pasta / ".rvgen" / f"sessao-{datetime.now():%Y%m%d-%H%M%S}")
        self._chamadas = 0
        self._tokens = [0, 0]
        self._lock_sessao = threading.Lock()
        self._fase_fluxo: int | None = None
        self._ultima_exploracao_falha: dict[str, Any] | None = None
        self._dependencias_semanticas_revisadas: set[str] = set()

    # -- utilitarios -------------------------------------------------------

    def relatar(self, texto: str) -> None:
        """Renderiza mensagens em árvore de acordo com o escopo ativo."""
        if not self._escopos_log:
            self._relatar_bruto(texto)
            return
        prefixo = "│  " * len(self._escopos_log)
        linhas = texto.splitlines() or [""]
        self._relatar_bruto("\n".join(prefixo + linha.lstrip() for linha in linhas))

    def _definir_escopos_log(self, *escopos: tuple[str, str]) -> None:
        """Define a cadeia pai/filho que será persistida nos próximos eventos."""
        self._escopos_log = [{"id": identificador, "titulo": titulo}
                             for identificador, titulo in escopos]
        for nivel, (_, titulo) in enumerate(escopos):
            self._relatar_bruto(f"{'│  ' * nivel}└─ {titulo}")

    def _acrescentar_escopo_log(self, identificador: str, titulo: str) -> None:
        """Abre um filho persistente até a próxima redefinição de escopos."""
        pai = self._escopos_log[-1]["id"] if self._escopos_log else None
        prefixo = "│  " * len(self._escopos_log)
        self._relatar_bruto(f"{prefixo}└─ {titulo}")
        self._escopos_log.append({"id": identificador, "titulo": titulo})
        self._log({"evento": "escopo_aberto", "escopo": identificador,
                   "pai": pai, "titulo": titulo})

    @contextmanager
    def _escopo_log(self, identificador: str, titulo: str):
        pai = self._escopos_log[-1]["id"] if self._escopos_log else None
        self._escopos_log.append({"id": identificador, "titulo": titulo})
        prefixo = "│  " * (len(self._escopos_log) - 1)
        self._relatar_bruto(f"{prefixo}└─ {titulo}")
        self._log({"evento": "escopo_aberto", "escopo": identificador, "pai": pai,
                   "titulo": titulo})
        try:
            yield
        finally:
            self._escopos_log.pop()

    def _log(self, evento: dict) -> None:
        if self._escopos_log:
            evento = {"escopo": self._escopos_log[-1]["id"],
                      "pai": (self._escopos_log[-2]["id"]
                              if len(self._escopos_log) > 1 else None), **evento}
        evento = {"t": datetime.now().isoformat(timespec="seconds"), **evento}
        with self._lock_sessao:
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
        destino = self._destino(rel)
        anterior = destino.read_text(encoding="utf-8") if destino.exists() else None
        destino.write_text(conteudo, encoding="utf-8")
        if anterior != conteudo:
            self.relatar(f"  VHDL modificado: {rel}")
            self._log({"evento": "vhdl_modificado", "arquivo": rel,
                       "anterior_existia": anterior is not None})

    def _ler(self, rel: str) -> str:
        p = self._destino(rel)
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def _caminho_teste(self, bloco: dict) -> Path:
        """Destino fixo, fora de src, para um testbench gerado."""
        return self.sessao / "testes" / f"test_{bloco['name']}.py"

    def _caminho_snapshot_teste(self, teste: Path) -> Path:
        """Última suíte aprovada, persistida para rollback após uma retomada."""
        return self.sessao / "testes_aprovados" / teste.name

    def _caminho_especificacao(self, bloco: dict) -> Path:
        return self.sessao / "component_specs" / f"{bloco['name']}.comp_spec.txt"

    def _portas_de_instrucao_rv32i(self, bloco: dict) -> list[str]:
        """Entradas de palavra RV32I declaradas semanticamente, não por nome do bloco."""
        especificacao = self._ler_especificacao(bloco)
        if not re.search(r"\brv32i\b", especificacao, re.IGNORECASE):
            return []
        interface = self._interface_do_bloco(bloco)
        portas = re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*in\s+std_logic_vector\s*\(\s*31\s+downto\s+0\s*\)",
            interface, re.IGNORECASE)
        return [porta for porta in portas if re.fullmatch(
            r"(?:instr(?:uction)?|insn)(?:_data)?", porta, re.IGNORECASE)]

    def _programa_rv32i_sequencial(self, bloco: dict) -> bool:
        """Só a interface com PC externo precisa de programa e labels."""
        if not self._portas_de_instrucao_rv32i(bloco):
            return False
        return bool(re.search(r"\binstr_addr\s*:\s*out\s+std_logic_vector",
                               self._interface_do_bloco(bloco), re.IGNORECASE))

    def _montador_de_estimulos(self) -> str:
        """Nome da capacidade Cocotb correspondente à ISA da CPU atual."""
        return f"assemble_{self.isa}"

    def _capacidade_assembly_rv32i(self, bloco: dict) -> str:
        portas = self._portas_de_instrucao_rv32i(bloco)
        if not portas:
            return ""
        montador = self._montador_de_estimulos()
        isa = self.isa.upper()
        return (
            "\n\nAvailable test capability — `riscv_program`:\n"
            f"This component declares {isa} instruction input(s): {', '.join('`' + p + '`' for p in portas)}. "
            "When the new case needs an instruction or program, write assembly source only and import "
            f"`{montador}` from `rvgen.riscv_asm`. Call `{montador}` with a small multiline "
            "assembly string; it returns `{pc: uint32_instruction}`. Fetch its word using the DUT PC. "
            "Do NOT calculate instruction encodings, use instruction hexadecimal literals, write bit fields, "
            f"or use pseudoinstructions/directives. Labels and real {isa} mnemonics are allowed. "
            + ("This is a sequential instruction-memory interface: branch and JAL targets MUST be labels, "
               "never numeric operands, so the assembler resolves the target. Never use `nop`; write "
               "`addi x0, x0, 0` instead. For a JAL +8 fixture at PC 0, use exactly "
               "`jal x1, target\\naddi x0, x0, 0\\ntarget: jal x0, target`: `target` is then address 8. "
               if self._programa_rv32i_sequencial(bloco) else
               "This is a single-instruction interface: numeric immediates (including negative branch/JAL "
               "offsets) are allowed and should be used when testing decoded immediate fields. ") +
             f"Example: `program = {montador}('addi x1, x0, 1\\njal x0, done\\ndone: jal x0, done')`.\n")

    def _novo_caso_usa_assembly_rv32i(self, codigo: str, nomes: set[str],
                                       portas: list[str], *, exigir_labels_controle: bool = False) -> bool:
        """Impede que uma expansão RV32I volte a inventar palavras de instrução."""
        arvore = ast.parse(codigo)
        funcoes = [no for no in arvore.body if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
                    and no.name in nomes]
        chamadas = [no for funcao in funcoes for no in ast.walk(funcao)
                    if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and
                    no.func.id == self._montador_de_estimulos()]
        if not chamadas:
            return False
        try:
            for chamada in chamadas:
                if len(chamada.args) != 1:
                    return False
                fonte = ast.literal_eval(chamada.args[0])
                if not isinstance(fonte, str):
                    return False
                validar_assembly_riscv(fonte, isa=self.isa,
                                       exigir_labels_controle=exigir_labels_controle)
        except (ValueError, TypeError, ErroAssemblyRV32I):
            return False
        for funcao in funcoes:
            for no in ast.walk(funcao):
                if not isinstance(no, (ast.Assign, ast.AnnAssign)):
                    continue
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                valor = no.value
                for alvo in alvos:
                    if not (isinstance(alvo, ast.Attribute) and alvo.attr == "value" and
                            isinstance(alvo.value, ast.Attribute) and
                            isinstance(alvo.value.value, ast.Name) and alvo.value.value.id == "dut" and
                            alvo.value.attr in portas):
                        continue
                    if isinstance(valor, ast.Constant) and isinstance(valor.value, int) and valor.value:
                        return False
        return True

    def _motivos_estimulo_rv32i(self, codigo: str, nomes: set[str],
                                portas: list[str], *,
                                exigir_labels_controle: bool = False) -> list[dict[str, Any]]:
        """Explica por que um estímulo não satisfaz a política do montador."""
        arvore = ast.parse(codigo)
        funcoes = [no for no in arvore.body if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and no.name in nomes]
        motivos: list[dict[str, Any]] = []
        chamadas = [no for funcao in funcoes for no in ast.walk(funcao)
                    if isinstance(no, ast.Call) and isinstance(no.func, ast.Name) and
                    no.func.id == self._montador_de_estimulos()]
        if not chamadas:
            motivos.append({"kind": "missing_riscv_assembler_call",
                            "required": self._montador_de_estimulos()})
        for chamada in chamadas:
            if len(chamada.args) != 1:
                motivos.append({"kind": "invalid_riscv_assembler_arguments"})
                continue
            try:
                fonte = ast.literal_eval(chamada.args[0])
                if not isinstance(fonte, str):
                    raise ValueError("assembly source is not a literal string")
                validar_assembly_riscv(fonte, isa=self.isa,
                                       exigir_labels_controle=exigir_labels_controle)
            except (ValueError, TypeError, ErroAssemblyRV32I) as erro:
                motivos.append({"kind": "invalid_riscv_assembly_source", "detail": str(erro)})
        for funcao in funcoes:
            for no in ast.walk(funcao):
                if not isinstance(no, (ast.Assign, ast.AnnAssign)):
                    continue
                alvos = no.targets if isinstance(no, ast.Assign) else [no.target]
                for alvo in alvos:
                    if (isinstance(alvo, ast.Attribute) and alvo.attr == "value" and
                            isinstance(alvo.value, ast.Attribute) and
                            isinstance(alvo.value.value, ast.Name) and alvo.value.value.id == "dut" and
                            alvo.value.attr in portas and isinstance(no.value, ast.Constant) and
                            isinstance(no.value.value, int) and no.value.value):
                        motivos.append({"kind": "hand_encoded_instruction",
                                        "port": alvo.value.attr,
                                        "value": f"0x{no.value.value:08X}",
                                        "fix": "fetch every nonzero instruction from the assembled program"})
        return motivos

    def _expansao_testbench_concluida(self, bloco: dict) -> bool:
        """Indica se todos os casos incrementais da suíte já foram adicionados."""
        registro = self.sessao / "sessao.jsonl"
        if not registro.is_file():
            return False
        try:
            return any(json.loads(linha).get("evento") == "testbench_expansao_concluida" and
                        json.loads(linha).get("bloco") == bloco["name"]
                       for linha in registro.read_text(encoding="utf-8").splitlines())
        except (OSError, json.JSONDecodeError):
            return False

    @staticmethod
    def _testes_cocotb(codigo: str) -> dict[str, str]:
        """Representação estável das funções públicas de teste de uma suíte."""
        arvore = ast.parse(codigo)
        testes = {}
        for no in arvore.body:
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorado = any(
                (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and
                 d.func.attr == "test") or
                (isinstance(d, ast.Attribute) and d.attr == "test")
                for d in no.decorator_list)
            if decorado:
                testes[no.name] = ast.dump(no, include_attributes=False)
        return testes

    @staticmethod
    def _fontes_testes_cocotb(codigo: str) -> dict[str, str]:
        """Texto executável completo de cada teste, incluindo decoradores."""
        linhas = codigo.splitlines(keepends=True)
        arvore = ast.parse(codigo)
        fontes: dict[str, str] = {}
        for no in arvore.body:
            if not isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            decorado = any(
                (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and
                 d.func.attr == "test") or
                (isinstance(d, ast.Attribute) and d.attr == "test")
                for d in no.decorator_list)
            if decorado:
                inicio = min([no.lineno] + [d.lineno for d in no.decorator_list]) - 1
                fontes[no.name] = "".join(linhas[inicio:no.end_lineno])
        return fontes

    @staticmethod
    def _caminhos_dut_no_ast(codigo: str) -> set[str]:
        """Caminhos ``dut.*`` realmente lidos/escritos pelo Python, sem comentários."""
        achados: set[str] = set()
        for no in ast.walk(ast.parse(codigo)):
            if not isinstance(no, ast.Attribute):
                continue
            partes = [no.attr]
            valor = no.value
            while isinstance(valor, ast.Attribute):
                partes.append(valor.attr)
                valor = valor.value
            if isinstance(valor, ast.Name) and valor.id == "dut":
                achados.add("dut." + ".".join(reversed(partes)))
        return achados

    @classmethod
    def _smoke_cocotb_valido(cls, codigo: str) -> bool:
        """Impõe um ponto de partida pequeno e observável para a suíte."""
        try:
            ast.parse(codigo)
        except SyntaxError:
            return False
        return len(cls._testes_cocotb(codigo)) == 1

    @classmethod
    def _modulo_cocotb_valido(cls, codigo: str, *, um_teste: bool = False) -> bool:
        """Contrato mínimo comum a qualquer módulo Cocotb gerado pela LLM."""
        try:
            arvore = ast.parse(codigo)
        except SyntaxError:
            return False
        testes = [no for no in arvore.body if isinstance(no, ast.AsyncFunctionDef) and any(
            (isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == "test") or
            (isinstance(d, ast.Attribute) and d.attr == "test") for d in no.decorator_list)]
        if not testes or (um_teste and len(testes) != 1):
            return False
        for teste in testes:
            args = teste.args.args
            if len(args) != 1 or args[0].arg != "dut":
                return False
            if not any(isinstance(no, ast.Name) and no.id == "dut" for no in ast.walk(teste)):
                return False
        return True

    def _decidir_expansao_testbench(self, bloco: dict, teste: Path, *,
                                    interno: bool = False,
                                    rejeicao_anterior: str = "", casos_aprovados: int | None = None,
                                    contexto_suite: str | None = None) -> tuple[str, int] | None:
        """Compara evidência acumulada e plano antes de crescer a suíte.

        Retorna a instrução de um único caso pendente, ou ``None`` se o plano
        já possui evidência suficiente. A decisão é separada da escrita para
        impedir que o autor de testes amplie a suíte sem justificar a lacuna.
        """
        atual = contexto_suite or teste.read_text(encoding="utf-8", errors="replace")
        quantidade_atual = len(self._testes_cocotb(atual))
        # A suíte pública começa com smoke; a interna começa diretamente com
        # seus casos diagnósticos. O orçamento é sempre um teto, não uma meta.
        casos_ja_aprovados = (casos_aprovados if casos_aprovados is not None else
                              quantidade_atual if interno else max(0, quantidade_atual - 1))
        limite_de_casos = self.max_casos_internos if interno else self.max_casos_teste
        saldo_de_casos = max(0, limite_de_casos - casos_ja_aprovados)
        try:
            caminhos = json.loads((self.sessao / "hierarquia" /
                                  f"{bloco['name']}.json").read_text(encoding="utf-8")).get("paths", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            caminhos = []
        camada = ("This is the INTERNAL diagnostic-integration layer. Every case must read at "
                  "least one simulator-confirmed internal path; it is not normative public coverage. "
                  if interno else
                  "This is the normative PUBLIC layer. Use only declared ports; do not require internals. ")
        restricao = ("Use only the inventory below for internal probes. " if interno else
                     "Do not require implementation internals. ")
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Act as the evidence orchestrator for Cocotb suite `{teste.name}` of entity "
                 f"`{bloco['name']}`. {camada}Compare the CURRENT passing suite against the normative "
                "Test strategy below. Determine which strategy claims already have a concrete "
                "public-port witness, and whether exactly one further non-homogeneous case is "
                "needed. Order expansion by semantic complexity: choose the least complex missing "
                "behavior whose prerequisites already have passing witnesses. Complexity increases "
                "when a case depends on prior state, combines control classes, routes more than one "
                "value, or requires an additional transformation. Never skip directly to a case "
                "that needs untested prerequisites, and vary only one new semantic factor relative "
                "to the accumulated suite. A candidate that merely repeats the causal relation of "
                "an existing test, even with different literals, is not new evidence and must not "
                "be selected. A case has exactly one focal behavior. When that behavior is not "
                "directly observable through public ports, its stimulus may use the shortest "
                "support sequence and public witness transaction needed to establish or observe "
                "it. Label that sequence as support, assert only facts necessary to witness the "
                "focal behavior, and do not count the support behavior as newly covered. `New "
                 "factor` must name one behavior only, not a compound list joined by and/or. "
                 f"{restricao}Do not require exhaustive enumeration. "
                 f"Every {self.isa.upper()} instruction stimulus must be expressible as legal source accepted by "
                 f"`{self._montador_de_estimulos()}`; therefore do NOT select reserved, illegal, unallocated, or malformed "
                 "instruction encodings as a coverage gap. Those encodings have no legal assembly witness. "
                  f"Coverage budget: {casos_ja_aprovados} incremental case(s) already approved; the hard "
                  f"limit is {limite_de_casos}; at most {saldo_de_casos} further incremental case(s) "
                 "may be authorized. This is a ceiling, NOT a coverage target: return `complete` as soon "
                 "as evidence is adequate. Return JSON only matching the supplied schema. Use decision `complete` when every "
                 "declared semantic class and behavior-changing edge case has adequate evidence. "
                "For decision `add`, fill coverage_gap (the exact semantic class or edge case still "
                "without evidence), behavior, prerequisites, new_factor, stimulus, "
                 "support_witness_path, public_observations, and forbidden. `remaining` is the "
                 "positive number of remaining cases including this one; it MUST NOT exceed the available "
                 f"budget ({saldo_de_casos}). The stimulus must describe "
                "a scenario class only: do NOT calculate binary encodings, instruction words, "
                "hex literals, Python, Cocotb, clock edges, or test steps.\n\n"
                f"Normative semantic contract and Test strategy:\n{self._ler_especificacao(bloco)}\n\n"
                f"Public interface:\n```vhdl\n{self._interface_do_bloco(bloco)}\n```\n\n"
                f"Simulator-confirmed hierarchy inventory:\n{json.dumps(caminhos)}\n\n"
                f"Last rejected expansion (if any; replace its plan, do not repeat it):\n"
                f"{rejeicao_anterior or '(none)'}\n\n"
                f"Current passing suite:\n```python\n{atual}\n```")},
        ]
        self.relatar(f"  verificando cobertura incremental de {bloco['name']} ...")
        for _ in (1, 2):
            r = self._chamar("orquestracao_expansao_testbench",
                             teste.relative_to(self.pasta).as_posix(), mensagens,
                             schema=_SCHEMA_PLANO_EXPANSAO, temperatura=0.0)
            resposta = r.texto.strip()
            if resposta.upper() == "COMPLETE":
                return None
            try:
                plano_json = extrair_json(resposta)
            except (ErroLLM, AttributeError):
                plano_json = None
            if isinstance(plano_json, dict):
                if plano_json.get("decision") == "complete":
                    return None
                campos = ("behavior", "prerequisites", "new_factor", "stimulus",
                           "public_observations", "forbidden")
                restantes = plano_json.get("remaining")
                if plano_json.get("decision") == "add" and isinstance(restantes, int) \
                        and 0 < restantes <= saldo_de_casos \
                        and all(plano_json.get(campo) for campo in campos):
                    def texto(campo: str) -> str:
                        valor = plano_json.get(campo, "")
                        return "; ".join(map(str, valor)) if isinstance(valor, list) else str(valor)
                    plano = (f"Behavior: {texto('behavior')}\n"
                              f"Coverage gap: {texto('coverage_gap') or texto('behavior')}\n"
                              f"Prerequisites: {texto('prerequisites')}\n"
                             f"New factor: {texto('new_factor')}\n"
                             f"Stimulus: {texto('stimulus')}\n"
                             f"Support/witness path: {texto('support_witness_path')}\n"
                             f"Public observations: {texto('public_observations')}\n"
                             f"Forbidden: {texto('forbidden')}")
                    return plano, restantes
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Reply only with valid JSON matching the schema. Do not calculate encodings "
                            "or write test steps. Respect the stated remaining coverage budget."}]
        raise ErroGeracao(f"o orquestrador nao decidiu a proxima expansao de {bloco['file']}")

    @staticmethod
    def _resumo_plano_incremental(plano: str, limite: int = 260) -> str:
        """Resumo estável, de uma linha, do plano recebido do orquestrador."""
        campos: dict[str, str] = {}
        for linha in plano.splitlines():
            chave, sep, valor = linha.partition(":")
            if sep:
                campos[chave.strip().lower()] = " ".join(valor.split())
        partes = [
            f"lacuna: {campos.get('coverage gap') or campos.get('behavior', 'não informada')}",
            f"fator: {campos['new factor']}" if campos.get("new factor") else "",
            f"estímulo: {campos['stimulus']}" if campos.get("stimulus") else "",
        ]
        texto = " — ".join(parte for parte in partes if parte)
        return texto[:limite - 1].rstrip() + "…" if len(texto) > limite else texto

    @staticmethod
    def _linha_curta(texto: Any, limite: int = 220) -> str:
        """Compacta evidência/hipótese para o console sem perder o JSON auditável."""
        linha = " ".join(str(texto or "").split())
        return linha[:limite - 1].rstrip() + "…" if len(linha) > limite else linha

    def _decidir_lote_expansao(self, bloco: dict, teste: Path, *, tamanho: int,
                                rejeicao_anterior: str = "", casos_aprovados: int | None = None,
                                contexto_suite: str | None = None) -> list[str] | None:
        """Planeja um lote de lacunas mutuamente independentes sobre a mesma suíte."""
        atual = contexto_suite or teste.read_text(encoding="utf-8", errors="replace")
        existentes = (max(0, len(self._testes_cocotb(atual)) - 1)
                      if casos_aprovados is None else casos_aprovados)
        saldo = self.max_casos_teste - existentes
        if saldo <= 0:
            return None
        limite = min(tamanho, saldo)
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Act as the coverage orchestrator for `{teste.name}` of `{bloco['name']}`. "
                f"Choose a batch of at most {limite} independent public-port {self.isa.upper()} test cases. "
                "Every case must have exactly one distinct focal behavior, must depend only on witnesses "
                "already present in the CURRENT passing suite, and must be independently executable. "
                "Do not choose reserved, illegal, or malformed instruction encodings: each instruction "
                f"must be expressible by legal source accepted by `{self._montador_de_estimulos()}`. "
                 f"There are {existentes} approved incremental cases and {saldo} slots left; this is a "
                 "ceiling, not a target. Reply ONLY valid JSON: never use YAML, Markdown, prose, or code "
                 "fences. Return `complete` when adequate evidence exists. For `add_batch`, "
                 "return one to the stated limit of cases, each with decision `add`, remaining, coverage_gap, "
                 "behavior, prerequisites, new_factor, stimulus, support_witness_path, public_observations, "
                 "and forbidden. `remaining` is advisory only and may be zero for the final available case.\n\n"
                 "Use exactly one of these top-level JSON envelopes (literal JSON, without fences):\n"
                 "{\"decision\":\"complete\",\"cases\":[]}\n"
                 "or:\n"
                 "{\"decision\":\"add_batch\",\"cases\":[{\"decision\":\"add\","
                 "\"remaining\":1,\"coverage_gap\":\"one uncovered behavior\","
                 "\"behavior\":\"the required causal relation\",\"prerequisites\":[\"approved witness\"],"
                 "\"new_factor\":\"one focal factor\",\"stimulus\":\"legal source-level scenario\","
                 "\"support_witness_path\":\"shortest support path\","
                 "\"public_observations\":[\"observable output relation\"],"
                 "\"forbidden\":[\"unrelated behavior\"]}]}\n\n"
                 f"Normative contract and test strategy:\n{self._ler_especificacao(bloco)}\n\n"
                f"Last rejected candidate:\n{rejeicao_anterior or '(none)'}\n\n"
                f"CURRENT passing suite:\n```python\n{atual}\n```")},
        ]
        self.relatar(f"  planejando lote incremental de ate {limite} caso(s) para {bloco['name']} ...")
        r = self._chamar("orquestracao_lote_testbench", teste.relative_to(self.pasta).as_posix(),
                          mensagens, schema=_SCHEMA_LOTE_EXPANSAO, temperatura=0.0)
        try:
            resposta = extrair_json(r.texto)
        except (ErroLLM, AttributeError):
            raise ErroPlanoTeste("orquestrador de lote nao respondeu JSON valido")
        if not isinstance(resposta, dict):
            raise ErroPlanoTeste("orquestrador de lote nao respondeu um objeto JSON")
        # Alguns provedores preservam o conteúdo mas trocam o envelope por
        # {"add_batch": [...]}. É semanticamente equivalente ao contrato
        # canônico; normalize-o sem gastar outra rodada de planejamento.
        if "decision" not in resposta and isinstance(resposta.get("add_batch"), list):
            resposta = {"decision": "add_batch", "cases": resposta["add_batch"]}
            self._log({"evento": "lote_incremental_normalizado", "bloco": bloco["name"],
                       "formato": "add_batch"})
        if resposta.get("decision") == "complete":
            return None
        casos = resposta.get("cases")
        if resposta.get("decision") != "add_batch" or not isinstance(casos, list):
            raise ErroPlanoTeste("orquestrador de lote nao escolheu `add_batch` nem `complete`")
        planos: list[str] = []
        campos = ("behavior", "prerequisites", "new_factor", "stimulus",
                  "support_witness_path", "public_observations", "forbidden")
        for caso in casos[:limite]:
            if not isinstance(caso, dict) or caso.get("decision") != "add" or \
                    not all(caso.get(c) for c in campos):
                raise ErroPlanoTeste("orquestrador de lote devolveu caso incompleto")
            def texto(campo: str) -> str:
                valor = caso.get(campo, "")
                return "; ".join(map(str, valor)) if isinstance(valor, list) else str(valor)
            planos.append(
                f"Coverage gap: {texto('coverage_gap') or texto('behavior')}\n"
                f"Behavior: {texto('behavior')}\nPrerequisites: {texto('prerequisites')}\n"
                f"New factor: {texto('new_factor')}\nStimulus: {texto('stimulus')}\n"
                f"Support/witness path: {texto('support_witness_path')}\n"
                f"Public observations: {texto('public_observations')}\n"
                f"Forbidden: {texto('forbidden')}")
        if not planos:
            raise ErroPlanoTeste("orquestrador de lote devolveu `add_batch` vazio")
        return planos

    def _registrar_plano_incremental(self, bloco: dict, *, camada: str,
                                     numero: int, plano: str) -> None:
        """Mantém uma trilha humana das lacunas que motivaram cada caso."""
        destino = self.sessao / "planos_incrementais" / f"{bloco['name']}.md"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with destino.open("a", encoding="utf-8") as arquivo:
            arquivo.write(f"## {camada.capitalize()} — incremento {numero}\n\n{plano}\n\n")

    def _casos_publicos_isolados(self, bloco: dict) -> list[Path]:
        raiz = self.sessao / "testes_casos" / bloco["name"] / "publicos"
        return sorted(raiz.glob("*.py")) if raiz.exists() else []

    def _casos_internos_isolados(self, bloco: dict) -> list[Path]:
        raiz = self.sessao / "testes_casos" / bloco["name"] / "internos"
        return sorted(raiz.glob("*.py")) if raiz.exists() else []

    def _pendentes_publicos_da_ultima_sessao(self, bloco: dict) -> list[Path]:
        """Recupera falhas do último lote interrompido para não perdê-las na retomada."""
        registro = self.sessao / "sessao.jsonl"
        try:
            eventos = [json.loads(linha) for linha in registro.read_text(encoding="utf-8").splitlines()]
        except (OSError, json.JSONDecodeError):
            return []
        execucoes = [e for e in eventos if e.get("evento") == "candidato_lote_executado" and
                      e.get("bloco") == bloco["name"] and isinstance(e.get("lote"), int)]
        if not execucoes:
            return []
        ultimo_lote = max(e["lote"] for e in execucoes)
        promovidos = {e.get("origem") for e in eventos
                      if e.get("evento") == "candidato_pendente_aprovado" and
                      e.get("bloco") == bloco["name"]}
        pendentes: list[Path] = []
        for evento in execucoes:
            if evento["lote"] != ultimo_lote or evento.get("passou"):
                continue
            rel = evento.get("arquivo")
            if isinstance(rel, str) and rel not in promovidos:
                caminho = self.pasta / rel
                if caminho.exists() and caminho not in pendentes:
                    pendentes.append(caminho)
        return pendentes

    def _contexto_publico_isolado(self, bloco: dict, smoke: Path) -> str:
        """Evidência aprovada usada pelo planejador sem entregar arquivos à LLM para edição."""
        partes = [f"## {smoke.name} (smoke)\n{smoke.read_text(encoding='utf-8', errors='replace')}"]
        for caso in self._casos_publicos_isolados(bloco):
            partes.append(f"## {caso.name} (approved isolated case)\n"
                          f"{caso.read_text(encoding='utf-8', errors='replace')}")
        return "\n\n".join(partes)

    def _contexto_interno_isolado(self, bloco: dict, base: Path) -> str:
        """Suíte diagnóstica acumulada, inclusive módulos isolados promovidos."""
        partes = [f"## {base.name} (internal base)\n"
                  f"{base.read_text(encoding='utf-8', errors='replace')}"]
        for caso in self._casos_internos_isolados(bloco):
            partes.append(f"## {caso.name} (approved internal diagnostic)\n"
                          f"{caso.read_text(encoding='utf-8', errors='replace')}")
        return "\n\n".join(partes)

    def _ler_especificacao(self, bloco: dict) -> str:
        caminho = self._caminho_especificacao(bloco)
        if not caminho.exists():
            raise ErroGeracao(f"falta a especificacao do componente {bloco['name']}")
        return caminho.read_text(encoding="utf-8")

    def _especificacoes_dependencias(self, bloco: dict, arq: dict) -> str:
        por_nome = {b["name"]: b for b in arq["blocks"]}
        partes = []
        for nome in bloco.get("depends_on", []):
            dep = por_nome[nome]
            partes.append(f"## {nome}.comp_spec.txt\n{self._ler_especificacao(dep)}")
        return "\n\n".join(partes) or "(none)"

    def _escrever_especificacao(self, bloco: dict, arq: dict) -> None:
        """Fixa o contrato semântico antes de VHDL e Cocotb o consumirem."""
        destino = self._caminho_especificacao(bloco)
        interface = self._interface_do_bloco(bloco)
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"Define the complete semantic contract for component `{bloco['name']}` before "
                "its VHDL is written. Return Markdown only. This contract will be normative for the "
                "VHDL implementation, Cocotb tests, and dependent components. Do not infer or "
                "mention implementation internals. State timing, reset behavior (or `none`), "
                "all input/output semantics, every opcode/selector encoding when applicable, "
                 "and boundary behavior. Use exactly these level-2 headings: `## Timing`, "
                 "`## Reset`, `## Behavior`, `## Operations`, `## Edge cases`, and "
                 "`## Test strategy`. "
                 "`## Operations` may say `none` only when there is no encoded selector.\n\n"
                 "The test strategy is normative and must be an executable evidence plan, not "
                 "generic coverage advice. For each public behavior that selects, indexes, routes, "
                 "packs, slices, extends, decodes, or transforms data: identify control classes, "
                 "state the causal input-to-output relation, require distinguishable source values "
                 "where a wrong selection could otherwise pass, and vary one semantic factor at a "
                 "time. Do not mention implementation internals.\n\n"
                f"Responsibility: {bloco['responsibility']}\n"
                f"Public interface:\n```vhdl\n{interface}\n```\n\n"
                "Semantic contracts of direct dependencies:\n"
                f"{self._especificacoes_dependencias(bloco, arq)}")},
        ]
        self.relatar(f"  definindo contrato semantico de {bloco['file']} ...")
        for _ in (1, 2):
            r = self._chamar("especificacao_componente",
                             destino.relative_to(self.pasta).as_posix(), mensagens)
            try:
                self._salvar_especificacao(bloco, self._corpo_especificacao_markdown(r.texto))
                self._log({"evento": "especificacao_componente", "bloco": bloco["name"],
                           "arquivo": destino.relative_to(self.pasta).as_posix()})
                return
            except (ErroLLM, KeyError, AttributeError, TypeError):
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                            {"role": "user", "content":
                             "Return only complete Markdown with all six required ## headings."}]
        raise ErroGeracao(f"o modelo nao produziu a especificacao de {bloco['file']}")

    @staticmethod
    def _corpo_especificacao_markdown(texto: str) -> str:
        """Extrai e valida a parte variável de uma spec Markdown da LLM."""
        corpo = texto.strip()
        cerca = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*?)\n```", corpo,
                              re.IGNORECASE | re.DOTALL)
        if cerca:
            corpo = cerca.group(1).strip()
        secoes = ("## Timing", "## Reset", "## Behavior", "## Operations", "## Edge cases",
                  "## Test strategy")
        if any(corpo.count(secao) != 1 for secao in secoes):
            # Revisores externos frequentemente devolvem conteúdo correto com
            # títulos combinados como "Responsibility and timing". Normalize
            # apenas quando cada seção canônica puder ser identificada; assim
            # não descartamos uma revisão semântica válida por protocolo.
            partes = re.split(r"(?m)^##\s+(.+?)\s*$", corpo)
            encontradas: dict[str, str] = {}
            for indice in range(1, len(partes), 2):
                titulo = partes[indice].strip().lower()
                conteudo = partes[indice + 1].strip()
                destino = (
                    "Test strategy" if "test" in titulo and "strateg" in titulo else
                    "Edge cases" if "edge" in titulo else
                    "Operations" if "operation" in titulo or "encoding" in titulo else
                    "Reset" if "reset" in titulo else
                    "Timing" if "timing" in titulo else
                    "Behavior" if "behavior" in titulo or "responsibility" in titulo else None)
                if destino and conteudo and destino not in encontradas:
                    encontradas[destino] = conteudo
            # "Responsibility and timing" traz ambos os assuntos; a seção de
            # comportamento recebe o mesmo texto somente se não havia uma
            # seção própria. Reset é explicitamente "none" para componentes
            # combinacionais, quando o revisor o omitiu.
            if "Timing" in encontradas and "Behavior" not in encontradas:
                encontradas["Behavior"] = encontradas["Timing"]
            if "Reset" not in encontradas:
                encontradas["Reset"] = "none"
            nomes = tuple(secao.removeprefix("## ") for secao in secoes)
            if not all(nome in encontradas for nome in nomes):
                raise ErroLLM("spec Markdown sem as secoes obrigatorias")
            corpo = "\n\n".join(f"## {nome}\n{encontradas[nome]}" for nome in nomes)
        # Na revisão, alguns modelos repetem todo o contrato que receberam,
        # incluindo cabeçalho, interface e responsabilidade. Essas partes
        # pertencem ao agente; retemos o contrato a partir de Timing, incluindo
        # a estratégia de teste que agora é parte normativa da spec.
        inicio = corpo.index("## Timing")
        return corpo[inicio:].strip()

    def _salvar_especificacao(self, bloco: dict, corpo: str) -> None:
        """Acrescenta interface fixa ao corpo Markdown semântico da LLM."""
        interface = self._interface_do_bloco(bloco)
        linhas = [f"# Component semantic contract: {bloco['name']}", "",
                  "## Public interface", "```vhdl", interface, "```", "",
                  "## Responsibility", bloco["responsibility"], "", corpo]
        destino = self._caminho_especificacao(bloco)
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("\n".join(linhas) + "\n", encoding="utf-8")

    @staticmethod
    def _completar_revisao_de_spec(texto: str, anterior: str) -> tuple[str, tuple[str, ...]]:
        """Completa seções imutáveis omitidas numa revisão de contrato.

        Uma revisão corretiva pode explicitar apenas as seções que mudaram. É
        seguro reter uma seção do contrato anterior somente quando a resposta
        já fornece Timing, Reset, Behavior e Test strategy completos e omite
        por inteiro ``Operations`` e/ou ``Edge cases``; nunca inventamos uma
        seção que o revisor tentou, mas falhou, em estruturar.
        """
        def sem_cerca(valor: str) -> str:
            valor = valor.strip()
            cerca = re.fullmatch(r"```(?:markdown|md)?\s*\n(.*?)\n```", valor,
                                 re.IGNORECASE | re.DOTALL)
            return cerca.group(1).strip() if cerca else valor

        candidato = sem_cerca(texto)
        secoes = ("Timing", "Reset", "Behavior", "Operations", "Edge cases", "Test strategy")
        obrigatorias_na_revisao = ("Timing", "Reset", "Behavior", "Test strategy")
        if any(candidato.count(f"## {secao}") > 1 for secao in secoes):
            raise ErroLLM("revisao Markdown repete secao obrigatoria")
        if any(candidato.count(f"## {secao}") != 1 for secao in obrigatorias_na_revisao):
            raise ErroLLM("revisao Markdown sem secoes semanticas essenciais")
        faltantes = tuple(secao for secao in secoes if f"## {secao}" not in candidato)
        if not faltantes:
            return Agente._corpo_especificacao_markdown(candidato), ()

        corpo_anterior = Agente._corpo_especificacao_markdown(anterior)
        preservadas: list[str] = []
        for secao in faltantes:
            trecho = re.search(rf"(?ms)^## {re.escape(secao)}\s*$\n(.*?)(?=^##\s|\Z)",
                               corpo_anterior)
            if trecho is None or not trecho.group(1).strip():
                raise ErroLLM(f"secao anterior ausente: {secao}")
            candidato += f"\n\n## {secao}\n{trecho.group(1).strip()}"
            preservadas.append(secao)
        return Agente._corpo_especificacao_markdown(candidato), tuple(preservadas)

    def _revisar_especificacao(self, bloco: dict, evidencia: str, arq: dict | None = None) -> None:
        """Altera explicitamente o contrato após evidência de conflito semântico."""
        anterior = self._ler_especificacao(bloco)
        fonte = self._ler(bloco["file"])
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"Review the semantic contract for component `{bloco['name']}`. A component "
                 "specification review identified a contract conflict, not merely a VHDL or Cocotb "
                 "bug. Return replacement Markdown with the required "
                 "six level-2 headings, exactly: `## Timing`, `## Reset`, `## Behavior`, "
                  "`## Operations`, `## Edge cases`, and `## Test strategy`. Do not include "
                  "Public interface or Responsibility: the agent retains those fixed sections. "
                  "Preserve correct behavior; make every changed encoding or semantic "
                 "rule explicit. The public entity and ports are fixed and must not change. "
                 "Selector encodings of direct dependencies are private contracts: do not require "
                 "different entities to share a numeric encoding. If their encodings differ, define "
                 "the CPU's explicit semantic adaptation between them, or derive the operation from "
                 "the instruction, without changing either dependency interface. Do not claim that "
                 "CPU public-port tests directly observe internal selectors.\n\n"
                 f"Failure evidence:\n{evidencia}\n\nCurrent contract:\n{anterior}\n\n"
                 "Semantic contracts of direct dependencies:\n"
                 f"{self._especificacoes_dependencias(bloco, arq) if arq else '(not available)'}\n\n"
                 f"Current VHDL (context only; do not preserve an incorrect behavior):\n"
                f"```vhdl\n{fonte}\n```")},
        ]
        self.relatar(f"  revisando contrato semantico de {bloco['file']} ...")
        # Resposta inválida da LLM é falha de protocolo, não uma razão para
        # abandonar a geração. Três rodadas tornam explícita a escalada sem
        # alterar VHDL nem aceitar contrato incompleto.
        for rodada in range(1, 4):
            for _ in (1, 2):
                r = self._chamar("revisao_especificacao",
                                 self._caminho_especificacao(bloco).relative_to(self.pasta).as_posix(), mensagens)
                try:
                    corpo, preservadas = self._completar_revisao_de_spec(r.texto, anterior)
                    self._salvar_especificacao(bloco, corpo)
                    self._log({"evento": "especificacao_revisada", "bloco": bloco["name"],
                               "arquivo": self._caminho_especificacao(bloco).relative_to(self.pasta).as_posix(),
                               "anterior": anterior, "evidencia": evidencia, "rodada": rodada,
                               "secoes_preservadas": list(preservadas)})
                    return
                except (ErroLLM, KeyError, AttributeError, TypeError):
                    pass
                mensagens += [{"role": "assistant", "content": r.texto},
                               {"role": "user", "content":
                                  "Return only Markdown with exactly these headings: ## Timing, ## Reset, "
                                  "## Behavior, ## Operations, ## Edge cases, and ## Test strategy."}]
            self._log({"evento": "revisao_especificacao_escalada", "bloco": bloco["name"],
                       "rodada": rodada, "evidencia": evidencia})
            self.relatar(f"  resposta de contrato invalida; replanejando revisao de "
                          f"{bloco['name']} ({rodada}/3) ...")
        raise ErroGeracao(f"nao foi possivel revisar a especificacao de {bloco['file']}")

    def _revisar_dependencias_citadas(self, bloco: dict, evidencia: str, arq: dict) -> bool:
        """Encaminha conflito de contrato ao bloco que o revisor realmente citou.

        Uma revisão do topo recebe as especificações das dependências. Se ela
        aponta uma contradição *dentro* delas, reescrever apenas o topo não
        pode resolver a evidência e criaria um loop de LLM.
        """
        if not re.search(r"\b(contradic|inconsisten|conflit|ambig)\w*", evidencia,
                         re.IGNORECASE):
            return False
        nomes = {str(nome).lower() for nome in bloco.get("depends_on", [])}
        citadas = [candidato for candidato in arq["blocks"]
                   if candidato["name"].lower() in nomes and
                   re.search(rf"\b{re.escape(candidato['name'])}\b", evidencia,
                             re.IGNORECASE)]
        if not citadas:
            return False
        for dependencia in citadas:
            self.relatar(f"  conflito semantico citado em {dependencia['file']}; "
                          "revisando a dependencia antes do topo ...")
            self._revisar_especificacao(dependencia, evidencia, arq)
            self._validar_especificacao_por_agente(dependencia, arq)
            self._dependencias_semanticas_revisadas.add(dependencia["name"])
            self._log({"evento": "dependencia_semantica_revisada",
                       "bloco_solicitante": bloco["name"],
                       "dependencia": dependencia["name"], "evidencia": evidencia})
        return True

    def _validar_especificacao_por_agente(self, bloco: dict, arq: dict) -> None:
        """Revisão semântica independente antes de qualquer VHDL ser escrito.

        O revisor julga apenas as afirmações feitas pela própria spec contra os
        contratos externos. Ele não escolhe blocos, portas internas ou uma
        microarquitetura alternativa.
        """
        for tentativa in range(1, self.tentativas_revisao_semantica + 1):
            spec = self._ler_especificacao(bloco)
            mensagens = [
                {"role": "system", "content": self.contrato_testes},
                {"role": "user", "content": (
                    f"Act as an independent semantic reviewer for proposed component "
                    f"`{bloco['name']}`. Check only whether claims made by this spec are "
                     "consistent with the CPU contract, the RV32I reference, the public entity, "
                     "and direct dependency contracts. Do NOT require a particular internal "
                     "decomposition, entity, signal name, opcode representation, or implementation. "
                     "Direct dependencies may use different private selector encodings; a parent "
                     "component may explicitly adapt between them. Reject an encoding mismatch only "
                     "when the proposed contract claims a direct connection but omits the required "
                     "adaptation. Do not require public CPU-port tests to observe internal selectors. "
                    "If the spec claims to decode an ISA field directly, verify that claim against "
                     "the reference. Reject a Test strategy that is generic boilerplate rather than "
                     "an evidence plan relating public inputs, control classes, and expected outputs. "
                     "Reply with exactly one of:\n"
                    "`APPROVED`\n"
                    "or\n"
                    "`REVISE` followed by concise bullet evidence of contradictions or ambiguity.\n\n"
                    f"Proposed specification:\n{spec}\n\n"
                    "Direct dependency specifications:\n"
                    f"{self._especificacoes_dependencias(bloco, arq)}")},
            ]
            self.relatar(f"  revisando semanticamente {bloco['file']} ...")
            r = self._chamar("revisao_semantica_especificacao",
                             self._caminho_especificacao(bloco).relative_to(self.pasta).as_posix(),
                             mensagens, temperatura=0.0)
            resposta = r.texto.strip()
            if resposta.upper() == "APPROVED":
                self._log({"evento": "especificacao_aprovada", "bloco": bloco["name"],
                           "arquivo": self._caminho_especificacao(bloco).relative_to(self.pasta).as_posix(),
                           "tentativa": tentativa})
                self.relatar(f"  contrato semantico de {bloco['name']:<11} ok")
                return
            m = re.match(r"^REVISE\b\s*(.*)$", resposta, re.IGNORECASE | re.DOTALL)
            if m and m.group(1).strip():
                evidencia = m.group(1).strip()
                self._log({"evento": "especificacao_reprovada", "bloco": bloco["name"],
                           "tentativa": tentativa, "evidencia": evidencia})
                if self._revisar_dependencias_citadas(bloco, evidencia, arq):
                    continue
                self._revisar_especificacao(bloco, evidencia, arq)
                continue
            # Um veredito inútil não deve virar uma alteração arbitrária da
            # spec. Uma nova chamada, com a resposta anterior explícita, é
            # permitida antes de interromper a geração.
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Reply exactly `APPROVED` or `REVISE` followed by bullet evidence."}]
        raise ErroGeracao("a revisao semantica nao aprovou "
                          f"{bloco['file']} em {self.tentativas_revisao_semantica} tentativas")

    def _interface_do_bloco(self, bloco: dict) -> str:
        """Declaração pública do DUT para prompts de Cocotb, sem sua arquitetura."""
        declaracoes = ct.declaracoes_de_entidade(self._ler(bloco["file"]))
        for declaracao in declaracoes:
            if re.search(rf"\bentity\s+{re.escape(bloco['name'])}\s+is\b", declaracao,
                         re.IGNORECASE):
                return declaracao
        # A decomposição já validada mantém o prompt útil mesmo se o arquivo
        # estiver temporariamente sem uma declaração extraível.
        return (f"entity {bloco['name']} is\n    port(\n        " +
                ";\n        ".join(bloco["ports"]) + "\n    );\nend " + bloco["name"] + ";")

    def _chamar(self, fase: str, alvo: str, mensagens: list[dict],
                 schema: dict | None = None,
                 temperatura: float | None = None) -> Resposta:
        """Uma chamada ao modelo, sempre registrada (FR-RV-50)."""
        with self._lock_sessao:
            self._chamadas += 1
        try:
            r = self.cliente.conversar(mensagens, schema=schema, temperatura=temperatura)
        except ErroLLM as e:
            self._log({"evento": "llm_erro", "fase": fase, "alvo": alvo, "erro": str(e)})
            raise
        with self._lock_sessao:
            self._tokens[0] += r.tokens_entrada or 0
            self._tokens[1] += r.tokens_saida or 0
        registradas = [{"role": m["role"], "content": "@contrato-testes.txt"}
                       if m["role"] == "system" and m["content"] == self.contrato_testes else
                       {"role": m["role"], "content": "@contrato.txt"}
                       if m["role"] == "system" and m["content"] == self.contrato else m
                       for m in mensagens]
        self._log({"evento": "llm", "fase": fase, "alvo": alvo,
                   "provedor": r.provedor, "modelo": r.modelo,
                    "tokens_entrada": r.tokens_entrada, "tokens_saida": r.tokens_saida,
                    "segundos": r.segundos, "cortes": r.cortes,
                    "motivo_finalizacao": r.motivo_finalizacao,
                    "temperatura": temperatura,
                    "mensagens": registradas,
                    "resposta": r.texto})
        if r.motivo_finalizacao == "length":
            self._log({"evento": "saida_truncada", "fase": fase, "alvo": alvo,
                       "provedor": r.provedor, "modelo": r.modelo,
                       "motivo_finalizacao": r.motivo_finalizacao,
                       "tokens_saida": r.tokens_saida,
                       "diagnostico": "o provedor encerrou a resposta por limite de comprimento"})
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

    @staticmethod
    def _requisito_integracao_top(blocos: list[dict]) -> str:
        """Instrução e evidência estáveis para composição obrigatória do top."""
        componentes = [b["name"] for b in blocos if b["name"] != ct.TOP]
        lista = ", ".join(componentes)
        exemplos = "\n".join(
            f"u_{nome} : entity work.{nome} port map ( ... );" for nome in componentes)
        return (
            "MANDATORY STRUCTURAL INTEGRATION REQUIREMENT:\n"
            f"`cpu` MUST instantiate and connect every generated component exactly once: {lista}.\n"
            "Use direct VHDL entity instantiation with named port association for every instance; "
            "the required form is `u_name : entity work.name port map (...)`. Declare every "
            "interconnecting signal and map every functional component port. Do NOT use `open` "
            "for a functional output. Do NOT reimplement decoder, register-file, ALU, branch, "
            "next-PC, or load/store behavior inside `cpu`: compose these entities instead. "
            "The only logic permitted directly in `cpu` is integration wiring and state not owned "
            "by a generated component. The generated VHDL is rejected unless every entity below "
            "appears as an `entity work.<name> ... port map` instance:\n"
            f"{exemplos}")

    def _integracao_top_valida(self, vhdl: str, arq: dict) -> tuple[bool, str]:
        faltantes = componentes_nao_integrados(vhdl, arq["blocks"])
        if not faltantes:
            return True, ""
        return False, ("CPU structural integration is incomplete. Missing required direct VHDL "
                       f"`entity work.<name> ... port map` instances: {', '.join(faltantes)}. "
                       "Do not implement those blocks internally; declare signals and instantiate them.")

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

    def _fase(self, numero: int) -> str:
        """Marcador de progresso; testes de componentes inserem uma quinta fase."""
        return f"[{numero}/{5 if self.testes_componentes else 4}]"

    def _mostrar_fluxo(self, fase: int, processo: str | None = None) -> None:
        """Mostra o caminho global e o processo pontual da rodada atual."""
        nomes = (["Arquitetura", "Componentes", "Testes", "spec-riscv-test", "Veredito"]
                 if self.testes_componentes else
                  ["Arquitetura", "Componentes", "spec-riscv-test", "Veredito"])
        if self._fase_fluxo != fase:
            partes = []
            for indice, nome in enumerate(nomes, start=1):
                estado = "✓" if indice < fase else "●" if indice == fase else "○"
                partes.append(f"{estado} {nome}")
            self.relatar("  fluxo: " + " ──▶ ".join(partes))
            self._fase_fluxo = fase
        if processo:
            self.relatar(f"  processo: {processo}")

    def _relatar_blocos(self, blocos: list[dict]) -> None:
        """Mostra o plano efetivo; a ordem ja respeita as dependencias."""
        for b in blocos:
            deps = ", ".join(b.get("depends_on", [])) or "nenhuma"
            self.relatar(f"    - {b['file']}: {b['name']} (depende de: {deps})")

    def _resumir_cpu_proposta(self) -> None:
        """Torna visível a configuração inferida de ``specs/cpu.md``.

        Esta etapa não consulta a LLM: ISA e microarquitetura já foram
        validadas pelo CLI antes de construir o agente.
        """
        quantidade = len(ct.instrucoes_da_isa(self.isa))
        self._mostrar_fluxo(1)
        self.relatar(f"{self._fase(1)} arquitetura: entendendo a CPU proposta ...")
        self.relatar(f"  CPU: {self.isa.upper()}, microarquitetura {self.microarquitetura}; "
                     f"{quantidade} instrucoes; top-level `{ct.TOP}`")
        self.relatar("  interface: barramento virtual de instrucao e dados, "
                     "sem memoria instanciada internamente")
        self._log({"evento": "cpu_proposta", "isa": self.isa,
                    "microarquitetura": self.microarquitetura,
                   "instrucoes": quantidade, "top": ct.TOP,
                   "memoria": "virtual"})

    # -- fases ---------------------------------------------------------------

    def _preparar_pasta(self) -> None:
        if self.pasta.exists() and not self.forcar and \
                any(p.name != ".rvgen" for p in self.pasta.iterdir()):
            raise ErroGeracao(f"{self.pasta} ja tem conteudo; use --forcar para "
                              f"sobrescrever os arquivos gerados")
        (self.pasta / "src").mkdir(parents=True, exist_ok=True)
        (self.sessao / "spec-riscv-test").mkdir(parents=True, exist_ok=True)
        (self.sessao / "contrato.txt").write_text(self.contrato, encoding="utf-8")
        (self.sessao / "testes.md").write_text(ct.texto_de_testes() + "\n", encoding="utf-8")
        (self.sessao / "contrato-testes.txt").write_text(self.contrato_testes, encoding="utf-8")
        if self.descricao:
            (self.pasta / "descricao.md").write_text(
                "# Descricao da CPU pedida ao modelo\n\n"
                "Texto livre passado a `rvgen gerar` (FR-RV-52). NAO verificado pelo\n"
                "rvverify: o veredito julga so o contrato; o mapeamento destes pedidos\n"
                "para os blocos, em `architecture.json` (`requests`), e declaracao do\n"
                "modelo.\n\n" + self.descricao + "\n", encoding="utf-8")

    def _inventariar_instrucoes(self) -> list[dict]:
        esperadas = ct.instrucoes_da_isa(self.isa)
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                "Document the CPU instructions before decomposition. Answer ONLY JSON: "
                '{"instructions": [{"mnemonic", "description"}]}. '
                "Give one concise implementation-oriented description for every mnemonic, "
                f"with no extras. Document these mnemonics: {', '.join(esperadas)}.")},
        ]
        self.relatar("  extraindo instrucoes da CPU ...")
        motivo = ""
        for _ in (1, 2):
            r = self._chamar("instrucoes", "architecture.json", mensagens,
                             schema=SCHEMA_INSTRUCOES)
            try:
                instrucoes, motivo = validar_instrucoes(extrair_json(r.texto), self.isa)
            except ErroLLM as e:
                instrucoes, motivo = None, str(e)
            if instrucoes:
                self._log({"evento": "instrucoes", "quantidade": len(instrucoes)})
                self.relatar(f"  instrucoes: {len(instrucoes)} documentadas para architecture.json")
                return instrucoes
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            f"Invalid inventory: {motivo}. Send it again."}]
        raise ErroGeracao(f"o modelo nao produziu inventario de instrucoes valido: {motivo}")

    def _planejar(self, instrucoes: list[dict]) -> dict:
        base = {"design": self.nome, "microarquitetura": self.microarquitetura, "isa": self.isa,
                "top": ct.TOP}
        if self.descricao:
            base.update(descricao=self.descricao, requests=[],
                        requests_note="declared by the model; NOT verified by rvverify")
        pedidos = (
            "\nAlso answer `requests`: one entry per item of the designer's "
            "description, with the `blocks` that implement it and `how`; if the "
            "contract prevents an item, say so in `how` and leave `blocks` empty."
            if self.descricao else "")
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"{self._texto_exemplo()}{self._texto_descricao()}"
                f"Instruction inventory (must be covered by the blocks): "
                f"{json.dumps(instrucoes, ensure_ascii=False)}\n\n"
                f"Decompose this {self.microarquitetura} {self.isa.upper()} CPU into hardware "
                f"blocks. Answer ONLY with JSON: {{\"blocks\": [{{\"name\", "
                f"\"responsibility\", \"ports\", \"depends_on\", \"design_rationale\"}}], "
                f"\"notes\"}}.\nRules: 2 to 8 blocks; each block becomes "
                f"src/<name>.vhd with `entity <name>`; lowercase names; never "
                f"reuse a provided entity ({', '.join(sorted(ct.ENTIDADES_RESERVADAS))}); "
                  f"the LAST block is `{ct.TOP}`, the top level that instantiates the "
                  f"other generated blocks and exposes the contract bus ports; `ports` are VHDL port "
                f"declarations such as \"clk : in std_logic\"; do NOT emit a `satisfies` "
                 f"field or enumerate FR-RV IDs; `design_rationale` justifies the "
                 f"block by area, speed or verifiability; `depends_on` lists only "
                  f"generated block names required before this block (use [] for leaves).{pedidos}")},
        ]
        motivo = ""
        self.relatar("  arquitetura: decompondo a CPU em blocos ...")
        for tentativa in (1, 2):
            r = self._chamar("decomposicao", "architecture.json", mensagens,
                             schema=_schema_arquitetura(bool(self.descricao)))
            try:
                bruta = extrair_json(r.texto)
            except ErroLLM as e:
                bruta, motivo = None, str(e)
            blocos, motivo = validar_arquitetura(bruta) if bruta is not None else (None, motivo)
            if blocos:
                arq = dict(base, origem="modelo", blocks=blocos,
                           notes=str((bruta or {}).get("notes", "")))
                if self.descricao:
                    arq["requests"] = _pedidos(bruta)
                self.relatar(f"  decomposicao: {len(blocos)} blocos propostos pelo modelo"
                              + (f", {len(arq['requests'])} pedidos da descricao mapeados"
                                 if self.descricao else ""))
                self._relatar_blocos(blocos)
                return arq
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                           f"That decomposition is invalid: {motivo}. Send the JSON again."}]
        self._log({"evento": "decomposicao_invalida", "motivo": motivo})
        raise ErroGeracao(f"o modelo nao produziu uma decomposicao valida: {motivo}")

    def _escrever_bloco(self, bloco: dict, arq: dict, k: int = 1, n: int = 1) -> None:
        plano = "\n".join(
            f"- {b['file']}: entity {b['name']} -- {b['responsibility']}\n"
            f"  ports: {'; '.join(b['ports']) or '(see contract)'}\n"
            f"  depends on: {', '.join(b.get('depends_on', [])) or 'no generated block'}"
                for b in arq["blocks"])
        especificacao = self._ler_especificacao(bloco)
        topo = ("\n" + self._requisito_integracao_top(arq["blocks"])
                if bloco["name"] == ct.TOP else "")
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"{self._texto_exemplo()}{self._texto_descricao()}"
                f"Architecture of this CPU:\n{plano}\n\n"
                f"Entity declarations already written:\n"
                f"{self._declaracoes(arq['blocks'], exceto=bloco['file'])}\n\n"
                f"Normative semantic contract for this component:\n{especificacao}\n\n"
                "Semantic contracts of direct dependencies:\n"
                f"{self._especificacoes_dependencias(bloco, arq)}\n\n"
                f"Write the complete file {bloco['file']} implementing entity "
                f"{bloco['name']}.\nResponsibility: {bloco['responsibility']}\n"
                f"Ports: {'; '.join(bloco['ports']) or '(see contract)'}{topo}\n"
                "You have NO tools and must not inspect files, plan, ask questions, or "
                "announce future work. The architecture and declarations above are all the "
                "information available. Respond immediately with the complete compilable "
                "file in exactly one ```vhdl block; no prose before or after it.")},
        ]
        self.relatar(f"{self._fase(2)} escrevendo {bloco['file']} (arquivo {k} de {n}) ...")
        for tentativa in (1, 2):
            r = self._chamar("escrita", bloco["file"], mensagens)
            vhdl = extrair_vhdl(r.texto)
            top_ok, motivo_top = (self._integracao_top_valida(vhdl, arq)
                                  if vhdl and bloco["name"] == ct.TOP else (True, ""))
            if vhdl and re.search(rf"\bentity\s+{bloco['name']}\s+is\b", vhdl, re.IGNORECASE) and top_ok:
                self._escrever(bloco["file"], vhdl)
                self.relatar(f"  escrito  {bloco['file']} ({vhdl.count(chr(10))} linhas, "
                             f"{r.tokens_saida or '?'} tokens, {r.segundos} s)")
                return
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                             f"The previous response was unusable. {motivo_top} Do not analyze, inspect, plan, "
                             f"or discuss the task. Send the complete compilable file {bloco['file']} "
                            f"now in exactly one ```vhdl block containing `entity {bloco['name']} is`."}]
        raise ErroGeracao(f"o modelo nao produziu {bloco['file']} em 2 tentativas")

    def _escrever_testbench(self, bloco: dict) -> Path:
        """Cria primeiro um smoke test mínimo de interface para o componente."""
        destino = self._caminho_teste(bloco)
        interface = self._interface_do_bloco(bloco)
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Write a MINIMAL Cocotb smoke test `{destino.name}` for entity "
                f"`{bloco['name']}`. This is phase 1 of testing, not the complete suite. "
                f"It must test ONLY this entity through its ports, import cocotb, contain EXACTLY "
                f"one @cocotb.test() function and EXACTLY one Python `assert`. Test one direct "
                f"public input-to-output or reset-to-output relation only. Do not combine reset "
                f"with functional execution, execute an instruction sequence, test dependent state, "
                f"or use a store merely to observe another result. Drive every input to known values. "
                f"Verify every `dut.<name>` against the declared "
                f"ports before writing it. Do not modify, duplicate, or inspect the DUT source "
                f"internally. Responsibility: "
                f"{bloco['responsibility']}\nRequirements: {', '.join(bloco['satisfies'])}\n\n"
                f"Normative component semantic contract:\n{self._ler_especificacao(bloco)}\n\n"
                "Public DUT interface (the implementation is intentionally not provided):\n"
                f"```vhdl\n{interface}\n```\n\n"
                "Answer only with the complete smoke test in one ```python block.")},
        ]
        self.relatar(f"  gerando smoke test de {bloco['file']} ...")
        for _ in (1, 2):
            r = self._chamar("testbench", destino.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            try:
                if codigo and self._smoke_cocotb_valido(codigo):
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(codigo, encoding="utf-8")
                    self._log({"evento": "smoke_test_gerado", "bloco": bloco["name"],
                               "arquivo": destino.relative_to(self.pasta).as_posix()})
                    return destino
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                             "The smoke is invalid. Send one syntactically valid Cocotb module with "
                             "exactly one @cocotb.test() and exactly one assert, testing one direct "
                             "public relation only."}]
        raise ErroGeracao(f"o modelo nao produziu um smoke test valido para {bloco['file']}")

    def _ampliar_testbench(self, bloco: dict, teste: Path,
                           proximo_caso: str, rotulo: str | None = None) -> tuple[Path, bool]:
        """Acrescenta exatamente um caso semântico a uma suíte já aprovada.

        A expansão é deliberadamente incremental: cada versão acumulada deve
        passar antes de a próxima classe semântica poder ser acrescentada.
        """
        atual = teste.read_text(encoding="utf-8", errors="replace")
        testes_atuais = self._testes_cocotb(atual)
        interface = self._interface_do_bloco(bloco)
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Expand this already passing Cocotb smoke test for entity `{bloco['name']}` "
                "INCREMENTALLY: "
                "add exactly ONE new @cocotb.test() implementing the evidence-orchestrator "
                "instruction below. Use the existing suite as the primary API and timing example: "
                "reuse its valid Cocotb conventions and helpers where applicable, and do not "
                "reintroduce already-resolved driving, reset, clock, or port-access mistakes. "
                "Read the causal relation asserted by every existing test before writing the new "
                "one. The new test must be a genuine semantic evolution: exercise the orchestrated "
                "new factor on top of already witnessed prerequisites, not restate an existing "
                "relation with new literal values. "
                "Preserve every existing test function byte-for-byte in "
                "meaning (same name, body, assertions, and decorators). The new case must use "
                "distinguishable values and vary one semantic factor at a time. Do NOT enumerate "
                "homogeneous register indices, addresses, data values, or operand combinations; "
                "do not generate a Cartesian product. Do not add implementation "
                "internals; use only declared ports. When the plan has a Support/witness path, "
                "implement only the shortest such path needed to observe the focal behavior; do "
                "not claim its support operations as separately covered behavior. It may use multiple Python assertions only "
                "when they observe facets explicitly listed under `Public observations` in the "
                "single orchestrated plan; it must not use assertions to test a behavior listed "
                "under `Forbidden`. Return the complete module in one ```python "
                "block. If every behavior and edge case explicitly required by Test strategy is "
                "already represented, reply exactly `COMPLETE` and do not return Python.\n\n"
                f"Responsibility: {bloco['responsibility']}\n"
                f"Normative component semantic contract:\n{self._ler_especificacao(bloco)}\n\n"
                f"Evidence-orchestrator instruction for the ONE new case:\n{proximo_caso}\n\n"
                f"Public DUT interface:\n```vhdl\n{interface}\n```\n\n"
                f"{self._capacidade_assembly_rv32i(bloco)}\n"
                f"Passing smoke test:\n```python\n{atual}\n```")},
        ]
        prefixo = f"  {rotulo}: " if rotulo else "  "
        self.relatar(f"{prefixo}adicionando um caso ao testbench de {bloco['file']} ...")
        ultimo_candidato = "(nenhum código Python extraído)"
        for _ in (1, 2):
            r = self._chamar("ampliacao_testbench", teste.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            ultimo_candidato = (codigo or r.texto)[-3000:]
            try:
                if codigo:
                    ast.parse(codigo)
                    testes_novos = self._testes_cocotb(codigo)
                    preservados = all(testes_novos.get(nome) == corpo
                                      for nome, corpo in testes_atuais.items())
                    adicionados = set(testes_novos) - set(testes_atuais)
                    portas_instrucao = self._portas_de_instrucao_rv32i(bloco)
                    assembly_valido = (not portas_instrucao or
                                        self._novo_caso_usa_assembly_rv32i(
                                            codigo, adicionados, portas_instrucao,
                                            exigir_labels_controle=self._programa_rv32i_sequencial(bloco)))
                    if (preservados and len(testes_novos) == len(testes_atuais) + 1 and
                            assembly_valido):
                        teste.write_text(codigo, encoding="utf-8")
                        self._log({"evento": "testbench_caso_adicionado", "bloco": bloco["name"],
                                   "arquivo": teste.relative_to(self.pasta).as_posix(),
                                   "caso": next(iter(adicionados))})
                        return teste, True
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                              "Send one complete syntactically valid Python module "
                              "that preserves every existing test unchanged and adds exactly one new "
                              "@cocotb.test() function implementing only the structured plan. For an "
                              "RV32I instruction input, it must call `assemble_rv32i` and must not "
                              "drive a nonzero instruction literal directly."}]
        raise ErroPlanoTeste(
            f"candidato Cocotb recusado: nao preservou a suite ou violou o portao de assembly RV32I "
            f"em {bloco['file']}. Candidato rejeitado:\n```python\n{ultimo_candidato}\n```")

    def _escrever_caso_publico_isolado(self, bloco: dict, destino: Path, plano: str,
                                        referencia: Path | None, rotulo: str | None = None) -> Path:
        """Cria um único caso público autocontido, sem reescrever a suíte aprovada."""
        interface = self._interface_do_bloco(bloco)
        exemplo = (referencia.read_text(encoding="utf-8", errors="replace")
                   if referencia and referencia.is_file() else "(no prior smoke test available)")
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Write ONE new, standalone Cocotb module for entity `{bloco['name']}`. "
                "It must contain exactly one @cocotb.test() function implementing only the "
                "structured plan below. This file is isolated: do NOT reproduce, import, edit, "
                "or refer to other test functions. Include every import and local helper needed "
                "by this one test. Use only declared public DUT ports. The test must be independently "
                "reset/initialized and deterministic. It has one focal causal behavior; support "
                "instructions are not separate coverage. For RV32I instruction inputs, use legal "
                "source with `assemble_rv32i`; never hand-encode a nonzero instruction and use labels "
                "for branches or JAL. Return one complete Python module in a ```python block.\n\n"
                f"One new-case plan:\n{plano}\n\n"
                f"Normative contract:\n{self._ler_especificacao(bloco)}\n\n"
                f"Public interface:\n```vhdl\n{interface}\n```\n\n"
                f"{self._capacidade_assembly_rv32i(bloco)}\n"
                "A passing smoke test is supplied only as a Cocotb/timing convention reference; "
                "do not copy its test function:\n"
                f"```python\n{exemplo}\n```")},
        ]
        prefixo = f"  {rotulo}: " if rotulo else "  "
        self.relatar(f"{prefixo}gerando caso isolado para {bloco['file']} ...")
        ultimo = "(nenhum código Python extraído)"
        motivo_rejeicao: list[dict[str, Any]] = []
        for _ in range(3):
            r = self._chamar("caso_publico_isolado", destino.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            ultimo = (codigo or r.texto)[-3000:]
            try:
                if codigo:
                    ast.parse(codigo)
                    nomes = set(self._testes_cocotb(codigo))
                    portas_instrucao = self._portas_de_instrucao_rv32i(bloco)
                    assembly_valido = (not portas_instrucao or self._novo_caso_usa_assembly_rv32i(
                        codigo, nomes, portas_instrucao,
                        exigir_labels_controle=self._programa_rv32i_sequencial(bloco)))
                    if len(nomes) == 1 and assembly_valido:
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        destino.write_text(codigo, encoding="utf-8")
                        return destino
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Send exactly one syntactically valid, standalone Cocotb test module. "
                            "It must contain one @cocotb.test() and valid RV32I assembly."}]
        raise ErroPlanoTeste(
            f"candidato Cocotb isolado recusado: exige um unico teste e assembly RV32I valido em "
            f"{bloco['file']}. Candidato rejeitado:\n```python\n{ultimo}\n```")

    def _regressoes_oficiais_existentes(self) -> set[str]:
        """Nomes upstream que já têm um Cocotb de regressão nesta sessão."""
        registro = self.sessao / "sessao.jsonl"
        if not registro.is_file():
            return set()
        try:
            return {str(evento["teste_oficial"]) for linha in registro.read_text(
                encoding="utf-8").splitlines() if (evento := json.loads(linha)).get("evento") ==
                "regressao_oficial_gerada" and evento.get("teste_oficial")}
        except (OSError, ValueError, json.JSONDecodeError):
            return set()

    def _gerar_regressoes_oficiais(self, ex: Execucao, arq: dict) -> set[str]:
        """Materializa uma regressão Cocotb focada para cada falha upstream.

        O programa oficial continua sendo a autoridade. Estes módulos são uma
        reprodução pequena, criada antes de alterar VHDL, para encurtar os
        ciclos seguintes de diagnóstico e nunca para substituir a suíte.
        """
        rel = ex.relatorio or {}
        if "status" not in rel or rel.get("kind") or not isinstance(rel.get("results"), list):
            return set()
        cpu = next((bloco for bloco in arq["blocks"] if bloco["name"] == ct.TOP), None)
        if not cpu:
            return set()
        existentes = self._regressoes_oficiais_existentes()
        falhas = [item for item in rel["results"]
                   if isinstance(item, dict) and item.get("status") != "passed" and
                   str(item.get("test", "")).strip() not in existentes]
        geradas: set[str] = set()
        for indice, falha in enumerate(falhas, 1):
            teste_oficial = str(falha["test"])
            nome = re.sub(r"[^a-z0-9_]+", "_", teste_oficial.lower()).strip("_")
            destino = self.sessao / "regressoes_oficiais" / f"test_{nome}.py"
            evidencia = {
                chave: falha[chave] for chave in ("test", "message", "pc", "cycle", "test_case",
                                                    "last_instruction", "official_case")
                if chave in falha
            }
            plano = (
                f"Behavior: reproduce the architectural behavior rejected by official `{teste_oficial}`.\n"
                f"Coverage gap: official upstream failure evidence: {json.dumps(evidencia, ensure_ascii=False)}\n"
                "Prerequisites: reset, legal short setup program, and only the minimum external memory model.\n"
                "New factor: exactly the failing load/store or ISA behavior named by the official evidence.\n"
                "Stimulus: derive the smallest legal RV32I assembly scenario that distinguishes this behavior.\n"
                "Support/witness path: use public instruction/data ports; observe the focal transaction or a final store.\n"
                "Public observations: assert the exact architectural result/address/width/data needed for this one behavior.\n"
                "Forbidden: internal DUT paths, hand-encoded instructions, broad multi-behavior programs.")
            self.relatar(f"  regressao oficial {teste_oficial}: gerando Cocotb focado "
                          f"({indice}/{len(falhas)}) ...")
            try:
                caso = self._escrever_caso_publico_isolado(
                    cpu, destino, plano, self._caminho_teste(cpu), rotulo="regressao oficial")
                resultado = self.executor.rodar_componente(
                    self.pasta, componente=cpu["name"], teste=caso,
                    json_saida=self.sessao / "testes_resultados" / f"oficial-{nome}.json",
                    workdir=self.sessao / "sim" / f"regressao-oficial-{nome}",
                    build_root=self.sessao / "build" / f"regressao-oficial-{nome}")
                relatorio_caso = resultado.relatorio or {}
                reproduziu = _falha_de_assertion(resultado)
                self._log({"evento": "regressao_oficial_gerada", "teste_oficial": teste_oficial,
                           "arquivo": caso.relative_to(self.pasta).as_posix(), "reproduziu": reproduziu,
                           "relatorio": resultado.json_path.relative_to(self.pasta).as_posix(),
                            "evidencia": evidencia})
                geradas.add(teste_oficial)
                estado = "REPRODUZIU" if reproduziu else "nao reproduziu; preservada para revisao"
                self.relatar(f"  regressao oficial {teste_oficial}: {estado}")
            except ErroPlanoTeste as erro:
                self._log({"evento": "regressao_oficial_rejeitada", "teste_oficial": teste_oficial,
                           "motivo": str(erro)})
                self.relatar(f"  regressao oficial {teste_oficial}: rejeitada; mantendo evidencia oficial")
        return geradas

    def _regressoes_oficiais_reproduzidas(self) -> list[tuple[str, Path]]:
        """Retorna somente regressões focadas que falharam antes da correção.

        Um Cocotb que não reproduziu a falha upstream é evidência útil para
        revisão, mas não pode bloquear uma alteração VHDL. Já os que
        reproduziram são o portão rápido obrigatório antes de repetir a suíte
        oficial inteira.
        """
        registro = self.sessao / "sessao.jsonl"
        if not registro.is_file():
            return []
        encontradas: dict[str, Path] = {}
        try:
            eventos = [json.loads(linha) for linha in registro.read_text(
                encoding="utf-8").splitlines()]
        except (OSError, ValueError, json.JSONDecodeError):
            return []
        for evento in eventos:
            if evento.get("evento") != "regressao_oficial_gerada" or not evento.get("reproduziu"):
                continue
            nome = str(evento.get("teste_oficial", "")).strip()
            arquivo = str(evento.get("arquivo", "")).strip()
            if nome and arquivo:
                # O registro é histórico e não é uma autorização para acessar
                # caminhos arbitrários: regressões oficiais só vivem nesta raiz.
                caminho = self.sessao / "regressoes_oficiais" / Path(arquivo).name
                if caminho.is_file():
                    encontradas[nome] = caminho
        return sorted(encontradas.items())

    def _validar_regressoes_oficiais(self, arq: dict, iteracao: int,
                                     testes: set[str] | None = None) -> tuple[bool, str]:
        """Executa regressões upstream reproduzidas antes da suíte completa."""
        regressoes = self._regressoes_oficiais_reproduzidas()
        if testes is not None:
            regressoes = [(nome, caminho) for nome, caminho in regressoes if nome in testes]
        if not regressoes:
            return True, ""
        cpu = next((bloco for bloco in arq["blocks"] if bloco["name"] == ct.TOP), None)
        if not cpu:
            return True, ""
        self.relatar(f"  regressões oficiais focadas: executando {len(regressoes)} caso(s) antes da suíte ...")
        falhas: list[str] = []
        for indice, (teste_oficial, teste) in enumerate(regressoes, 1):
            nome = re.sub(r"[^a-z0-9_]+", "_", teste_oficial.lower()).strip("_")
            rotulo = f"it{iteracao:02d}-focado-{nome}"
            ex = self.executor.rodar_componente(
                self.pasta, componente=cpu["name"], teste=teste,
                json_saida=self.sessao / "testes_resultados" / f"{rotulo}.json",
                workdir=self.sessao / "sim" / f"regressao-oficial-{rotulo}",
                build_root=self.sessao / "build" / f"regressao-oficial-{rotulo}")
            passou = bool((ex.relatorio or {}).get("passed"))
            self._log({"evento": "regressao_oficial_revalidada", "teste_oficial": teste_oficial,
                       "arquivo": teste.relative_to(self.pasta).as_posix(), "passou": passou,
                       "iteracao": iteracao,
                       "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
            self.relatar(f"    focado {indice}/{len(regressoes)} {teste_oficial}: "
                         f"{'ok' if passou else 'FALHOU'} ({ex.segundos:.1f} s)")
            if not passou:
                detalhe = str((ex.relatorio or {}).get("detail") or ex.saida).strip()
                falhas.append(f"- {teste_oficial}: {detalhe[:800]}")
        if not falhas:
            return True, ""
        return False, "Focused official Cocotb regressions still fail after the VHDL change:\n" + "\n".join(falhas)

    def _proxima_regressao_oficial(self, ex: Execucao) -> str | None:
        """Mantém como foco uma falha upstream já materializada em Cocotb.

        O Cocotb pode passar sem reproduzir o cenário completo; isso não apaga
        a falha oficial nem transfere silenciosamente o foco para outro teste.
        """
        falhas = [str(resultado.get("test", "")).strip()
                  for resultado in (ex.relatorio or {}).get("results", [])
                  if isinstance(resultado, dict) and resultado.get("status") != "passed" and
                  str(resultado.get("test", "")).strip()]
        materializadas = self._regressoes_oficiais_existentes()
        if focal := next((nome for nome in falhas if nome in materializadas), None):
            return focal
        return falhas[0] if falhas else None

    def _escrever_caso_interno_isolado(self, bloco: dict, destino: Path, plano: str,
                                        caminhos: list[str], referencia: Path) -> Path:
        """Cria um diagnóstico interno autocontido sem tocar casos aprovados."""
        internos = {p for p in caminhos if p.count(".") == 1}
        portas = {f"dut.{nome}" for nome in re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*(?:in|out|inout)\b",
            self._interface_do_bloco(bloco), flags=re.IGNORECASE)}
        internos -= portas
        exemplo = referencia.read_text(encoding="utf-8", errors="replace")
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Write ONE new, standalone INTERNAL Cocotb diagnostic module for `{bloco['name']}`. "
                "It must contain exactly one @cocotb.test(), use public ports only to drive inputs, "
                "and read one or more exact confirmed internal paths below. Include all imports and "
                "helpers needed by this isolated file. It is diagnostic-only: do not reproduce or edit "
                "other tests. Use legal label-based RV32I assembly where instruction stimulus is needed.\n\n"
                f"One new-case plan:\n{plano}\n\n"
                f"Confirmed internal paths:\n{json.dumps(sorted(internos))}\n\n"
                f"{self._capacidade_assembly_rv32i(bloco)}\n"
                "Existing diagnostic is reference only; do not copy its test functions:\n"
                f"```python\n{exemplo}\n```")},
        ]
        ultimo = "(nenhum código Python extraído)"
        for _ in (1, 2):
            r = self._chamar("caso_interno_isolado", destino.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            ultimo = (codigo or r.texto)[-3000:]
            try:
                if not codigo:
                    motivo_rejeicao = [{"kind": "no_python_module"}]
                else:
                    ast.parse(codigo)
                    nomes = set(self._testes_cocotb(codigo))
                    acessos = self._caminhos_dut_no_ast(codigo)
                    sinais = {p for p in acessos if p.count(".") == 1}
                    nao_inventados = sorted(sinais - portas - internos)
                    usa_interno = bool(internos & acessos)
                    portas_instrucao = self._portas_de_instrucao_rv32i(bloco)
                    assembly_valido = (not portas_instrucao or self._novo_caso_usa_assembly_rv32i(
                        codigo, nomes, portas_instrucao,
                        exigir_labels_controle=self._programa_rv32i_sequencial(bloco)))
                    motivo_rejeicao = []
                    if not self._modulo_cocotb_valido(codigo, um_teste=True):
                        motivo_rejeicao.append({"kind": "invalid_cocotb_signature",
                                                "required": "one async @cocotb.test(dut) using dut"})
                    if nao_inventados:
                        motivo_rejeicao.append({"kind": "uninventoried_probe", "paths": nao_inventados,
                                                "allowed_internal_paths": sorted(internos)})
                    if not usa_interno:
                        motivo_rejeicao.append({"kind": "missing_internal_probe",
                                                "allowed_internal_paths": sorted(internos)})
                    if not assembly_valido:
                        motivo_rejeicao.extend(self._motivos_estimulo_rv32i(
                            codigo, nomes, portas_instrucao,
                            exigir_labels_controle=self._programa_rv32i_sequencial(bloco)))
                    if not motivo_rejeicao:
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        destino.write_text(codigo, encoding="utf-8")
                        return destino
            except SyntaxError as e:
                motivo_rejeicao = [{"kind": "python_syntax_error", "detail": str(e)}]
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "The candidate was rejected. Correct ONLY the testbench and preserve its "
                            "diagnostic stage. Structured validation errors:\n"
                            f"```json\n{json.dumps(motivo_rejeicao, ensure_ascii=False)}\n```\n"
                            "Use only listed inventory paths and valid label-based RV32I assembly."}]
        self._log({"evento": "diagnostico_interno_rejeitado", "bloco": bloco["name"],
                   "arquivo": destino.relative_to(self.pasta).as_posix(), "motivos": motivo_rejeicao})
        raise ErroPlanoTeste(
            f"candidato interno isolado recusado: exige um unico teste, probe VPI inventariado e "
            f"assembly RV32I valido em {bloco['file']}. Motivos estruturados:\n"
            f"```json\n{json.dumps(motivo_rejeicao, ensure_ascii=False)}\n```\n"
            f"Candidato rejeitado:\n```python\n{ultimo}\n```")

    def _ampliar_lote_paralelo(self, bloco: dict, teste: Path, planos: list[str],
                                arq: dict, lote: int) -> tuple[list[Path], list[Path]]:
        """Gera módulos isolados em paralelo e os executa, em ordem, um a um."""
        raiz = self.sessao / "testes_candidatos" / bloco["name"] / f"lote-{lote:03d}"
        raiz.mkdir(parents=True, exist_ok=True)
        destinos = [raiz / f"caso-{n:02d}.py" for n in range(1, len(planos) + 1)]
        posicao = {destino: n for n, destino in enumerate(destinos, 1)}
        self.relatar(f"  lote {lote}: gerando {len(planos)} candidato(s) em paralelo ...")
        self._log({"evento": "lote_incremental_iniciado", "bloco": bloco["name"],
                   "lote": lote, "casos": len(planos),
                   "diretorio": raiz.relative_to(self.pasta).as_posix()})

        gerados: list[Path] = []
        with ThreadPoolExecutor(max_workers=len(planos), thread_name_prefix="rvgen-candidato") as pool:
            futuros = {pool.submit(self._escrever_caso_publico_isolado, bloco, destino, plano, teste,
                                   f"lote {lote}, candidato {posicao[destino]}/{len(planos)}"): destino
                       for destino, plano in zip(destinos, planos)}
            for futuro in as_completed(futuros):
                destino = futuros[futuro]
                try:
                    futuro.result()
                    gerados.append(destino)
                    self._log({"evento": "candidato_lote_gerado", "bloco": bloco["name"],
                               "lote": lote, "arquivo": destino.relative_to(self.pasta).as_posix()})
                except ErroPlanoTeste as erro:
                    self.relatar(f"    candidato {posicao[destino]}/{len(planos)}: rejeitado — "
                                  f"{str(erro).splitlines()[0][:180]}")
                    self._log({"evento": "candidato_lote_rejeitado", "bloco": bloco["name"],
                               "lote": lote, "arquivo": destino.relative_to(self.pasta).as_posix(),
                               "motivo": str(erro)})

        def executar(destino: Path) -> tuple[Path, Execucao]:
            rotulo = f"{bloco['name']}-lote{lote:03d}-{destino.stem}"
            ex = self.executor.rodar_componente(
                self.pasta, componente=bloco["name"], teste=destino,
                json_saida=self.sessao / "testes_resultados" / f"{rotulo}.json",
                workdir=self.sessao / "sim" / f"componente-{rotulo}",
                build_root=self.sessao / "build" / f"componente-{rotulo}",
                fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None)
            return destino, ex

        aprovados: list[Path] = []
        reprovados: list[Path] = []
        if gerados:
            self.relatar(f"  lote {lote}: executando {len(gerados)} candidato(s) sequencialmente ...")
            for destino in sorted(gerados):
                destino, ex = executar(destino)
                passou = bool((ex.relatorio or {}).get("passed"))
                self._log({"evento": "candidato_lote_executado", "bloco": bloco["name"],
                           "lote": lote, "arquivo": destino.relative_to(self.pasta).as_posix(),
                           "codigo": ex.codigo, "passou": passou, "segundos": ex.segundos,
                           "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
                if passou:
                    aprovados.append(destino)
                    self.relatar(f"    candidato {posicao[destino]}/{len(planos)}: APROVADO "
                                  f"({ex.segundos:.1f} s)")
                else:
                    reprovados.append(destino)
                    detalhe = str((ex.relatorio or {}).get("detail") or ex.saida).splitlines()[0][:180]
                    self.relatar(f"    candidato {posicao[destino]}/{len(planos)}: FALHOU — {detalhe}")

        oficiais: list[Path] = []
        raiz_oficial = self.sessao / "testes_casos" / bloco["name"] / "publicos"
        for destino in aprovados:
            oficial = raiz_oficial / f"lote-{lote:03d}-{destino.name}"
            oficial.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(destino, oficial)
            oficiais.append(oficial)
        if oficiais:
            self._log({"evento": "lote_incremental_mesclado", "bloco": bloco["name"],
                       "lote": lote, "aprovados": len(oficiais), "reprovados": len(planos) - len(oficiais),
                       "arquivos": [p.relative_to(self.pasta).as_posix() for p in oficiais]})
            self.relatar(f"  lote {lote}: {len(oficiais)}/{len(planos)} candidato(s) aprovados; "
                          "casos isolados promovidos ...")
        else:
            self._log({"evento": "lote_incremental_sem_aprovados", "bloco": bloco["name"],
                       "lote": lote, "casos": len(planos)})
            self.relatar(f"  lote {lote}: nenhum candidato aprovado; retornando ao orquestrador ...")
        return oficiais, reprovados

    def _escrever_regressao(self, bloco: dict, evidencia: str, numero: int) -> Path:
        """Cria um teste novo e imutavel a partir de uma falha ja observada.

        O arquivo original que encontrou a falha nunca e editado. A regressao
        e separada para que uma correcao posterior sempre execute os dois.
        """
        destino = self.sessao / "regressoes" / f"test_{bloco['name']}_regressao_{numero:02d}.py"
        interface = self._interface_do_bloco(bloco)
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"A component test previously failed for {bloco['file']}. Create a NEW, "
                f"complete Cocotb regression module `{destino.name}` for entity `{bloco['name']}`. "
                "Do not modify or repeat an existing test file. Add one test for the exact "
                "failure evidence below and at least three closely related edge cases. Keep "
                "the expected value from the evidence whenever it is stated; never weaken an "
                "assertion to make the DUT pass. Use only DUT ports, import cocotb, and answer "
                "with one ```python block.\n\n"
                f"Failure evidence (immutable):\n{evidencia}\n\n"
                f"Normative component semantic contract:\n{self._ler_especificacao(bloco)}\n\n"
                f"Public DUT interface:\n```vhdl\n{interface}\n```")},
        ]
        for _ in (1, 2):
            r = self._chamar("regressao", destino.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            try:
                if codigo and self._modulo_cocotb_valido(codigo, um_teste=True):
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(codigo, encoding="utf-8")
                    self._log({"evento": "regressao_gerada", "bloco": bloco["name"],
                               "arquivo": destino.relative_to(self.pasta).as_posix(),
                               "evidencia": evidencia})
                    return destino
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                           "The regression module is invalid. Send a complete syntactically valid "
                           "Cocotb module in one ```python block."}]
        raise ErroGeracao(f"o modelo nao produziu uma regressao valida para {bloco['file']}")

    def _testes_existentes_do_bloco(self, bloco: dict) -> list[Path]:
        """Todas as provas Cocotb já aprovadas ou focalizadas de um bloco."""
        nome = bloco["name"]
        candidatos = [self._caminho_teste(bloco)]
        candidatos += self._casos_publicos_isolados(bloco)
        candidatos += self._casos_internos_isolados(bloco)
        candidatos += sorted((self.sessao / "regressoes").glob(f"test_{nome}_regressao_*.py"))
        candidatos += sorted((self.sessao / "testes_internos").glob(f"test_{nome}_interno_*.py"))
        return list(dict.fromkeys(teste for teste in candidatos if teste.is_file()))

    def _rodar_provas_do_bloco(self, bloco: dict, arq: dict, rotulo: str) -> tuple[bool, str]:
        """Reexecuta provas existentes sem planejar, ampliar ou corrigir testes."""
        testes = self._testes_existentes_do_bloco(bloco)
        if not testes:
            return False, f"nenhuma prova Cocotb existente para {bloco['file']}"
        falhas: list[str] = []
        self.relatar(f"  provas de {bloco['name']}: executando {len(testes)} teste(s) existentes ...")
        for indice, teste in enumerate(testes, 1):
            etiqueta = f"{rotulo}-{bloco['name']}-{indice:02d}"
            ex = self.executor.rodar_componente(
                self.pasta, componente=bloco["name"], teste=teste,
                json_saida=self.sessao / "testes_resultados" / f"{etiqueta}.json",
                workdir=self.sessao / "sim" / f"provas-{etiqueta}",
                build_root=self.sessao / "build" / f"provas-{etiqueta}",
                fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None)
            passou = bool((ex.relatorio or {}).get("passed"))
            self._log({"evento": "prova_bloco_executada", "bloco": bloco["name"],
                       "arquivo": teste.relative_to(self.pasta).as_posix(), "passou": passou,
                       "rotulo": rotulo, "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
            if not passou:
                falhas.append(f"- {teste.name}: {str((ex.relatorio or {}).get('detail') or ex.saida)[:1000]}")
        return not falhas, "\n".join(falhas)

    def _revisar_correcao_local(self, bloco: dict, regressao: Path,
                                 historico: list[str]) -> str:
        """Escala tentativas locais repetidas sem rediagnosticar toda a CPU."""
        tentativas = "\n\n".join(historico[-3:])
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"Act as a focused VHDL debugger for `{bloco['file']}` only. The component "
                "has a confirmed failing port-level Cocotb regression, but three attempted fixes "
                "were reverted because its own test suite still failed. Diagnose a NEW concrete "
                "root cause and propose a different minimal change with exact line references. "
                "Do not discuss other components and do not write VHDL.\n\n"
                f"Component contract:\n{self._ler_especificacao(bloco)}\n\n"
                f"Current VHDL:\n```vhdl\n{self._ler(bloco['file'])}\n```\n\n"
                f"Confirmed focal Cocotb regression:\n```python\n"
                f"{regressao.read_text(encoding='utf-8', errors='replace')}\n```\n\n"
                f"Rejected attempt history:\n{tentativas}")},
        ]
        self.relatar(f"  revisao local de {bloco['name']}: analisando tentativas rejeitadas ...")
        r = self._chamar("revisao_correcao_local", bloco["file"], mensagens)
        texto = r.texto.strip()
        self._log({"evento": "revisao_correcao_local", "bloco": bloco["name"],
                   "regressao": regressao.relative_to(self.pasta).as_posix(),
                   "historico": historico[-3:], "resposta": texto})
        return texto

    def _evidencia_componente(self, ex: Execucao, bloco: dict, arquivos: list[str]) -> tuple[str, str]:
        """Escolhe o VHDL e reduz resultado/log de teste a texto para a correcao."""
        rel = ex.relatorio or {}
        alvo = bloco["file"]
        diagnostico = str(rel.get("diagnostico") or "")
        if not (rel.get("compilacao") or {}).get("ok"):
            nomes = {PurePosixPath(a).name: a for a in arquivos}
            for erro in erros_do_log(diagnostico or ex.saida):
                if _nome_base(erro["arquivo"]) in nomes:
                    alvo = nomes[_nome_base(erro["arquivo"])]
                    break
        detalhe = str(rel.get("detail") or ex.saida[-2000:] or "testbench falhou")
        log = rel.get("log")
        texto = (f"Component test failed for entity {bloco['name']} ({bloco['file']}).\n"
                 f"Result: {detalhe}" + (f"\nLog: {log}" if log else "") +
                 (f"\n\nRelevant simulator log:\n```text\n{diagnostico}\n```"
                  if diagnostico else ""))
        return alvo, texto

    def _orientacao_interna_para_correcao(self, bloco: dict, evidencia: str) -> str:
        """Seleciona pistas internas para correção, sem tornar internals normativos.

        A resposta serve exclusivamente à LLM que corrige VHDL. Os sinais não
        são lidos pelo Cocotb de aprovação e não influenciam seu veredito.
        """
        fonte = self._ler(bloco["file"])
        inventario = self.sessao / "hierarquia" / f"{bloco['name']}.json"
        try:
            caminhos = json.loads(inventario.read_text(encoding="utf-8")).get("paths", [])
        except (OSError, json.JSONDecodeError, AttributeError):
            caminhos = []
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Act as an internal diagnostic planner for VHDL component `{bloco['name']}`. "
                "A public-port test has already failed. Select at most four internal signals or "
                "instance-port connections that are relevant to locating the public failure. "
                "This is diagnostic guidance for a VHDL repair only: do not propose Cocotb "
                "assertions, do not change the public contract, and do not assume signals absent "
                "from the source. Return JSON only: {\"probes\":[{\"signal\":\"exact VHDL identifier "
                "or instance.port\",\"purpose\":\"why it separates possible causes\"}]}.\n\n"
                f"Public failure evidence:\n{evidencia}\n\n"
                f"Simulator-confirmed hierarchy paths (may be empty):\n{json.dumps(caminhos)}\n\n"
                f"VHDL source:\n```vhdl\n{fonte}\n```")},
        ]
        try:
            r = self._chamar("diagnostico_interno_componente",
                             bloco["file"], mensagens, schema=_SCHEMA_PROBES_INTERNOS,
                             temperatura=0.0)
            resposta = extrair_json(r.texto)
            probes = resposta.get("probes", []) if isinstance(resposta, dict) else []
            validos = []
            for probe in probes if isinstance(probes, list) else []:
                if not isinstance(probe, dict):
                    continue
                sinal = str(probe.get("signal", "")).strip()
                proposito = str(probe.get("purpose", "")).strip()
                # Aceitamos apenas identificadores que tenham raiz textual na
                # fonte atual; isto impede o planejador de inventar hierarquia.
                raiz = sinal.split(".")[-1]
                exposto = sinal in caminhos
                if sinal and proposito and exposto and re.search(rf"\b{re.escape(raiz)}\b", fonte):
                    validos.append(f"- `{sinal}`: {proposito}")
            texto = "\n".join(validos) or "- no reliable internal probe identified"
            self._log({"evento": "diagnostico_interno_planejado", "bloco": bloco["name"],
                       "probes": validos})
            return ("\n\nInternal diagnostic guidance (non-normative; do not expose these in Cocotb):\n"
                    + texto)
        except (ErroLLM, AttributeError, TypeError):
            return "\n\nInternal diagnostic guidance unavailable; rely on the public failure evidence."

    def _inventariar_hierarquia(self, bloco: dict, arq: dict) -> list[str]:
        """Descobre caminhos VPI expostos, somente para diagnósticos internos."""
        destino = self.sessao / "diagnosticos" / f"test_{bloco['name']}_inventario.py"
        resultado = self.sessao / "hierarquia" / f"{bloco['name']}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        resultado.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text("""import cocotb
import json

@cocotb.test()
async def inventory_visible_hierarchy(dut):
    paths = []
    def visit(handle, path, depth):
        if depth > 2 or len(paths) >= 64:
            return
        try:
            children = list(handle)
        except Exception:
            children = []
        for child in children:
            name = getattr(child, "_name", None) or getattr(child, "name", None)
            if not name:
                continue
            child_path = path + "." + str(name)
            paths.append(child_path)
            visit(child, child_path, depth + 1)
    visit(dut, "dut", 0)
    cocotb.log.info("RVGEN_HIERARCHY=" + json.dumps(paths))
    assert True
""", encoding="utf-8")
        self.relatar(f"  inventariando hierarquia interna de {bloco['name']} ...")
        ex = self.executor.rodar_componente(
            self.pasta, componente=bloco["name"], teste=destino,
            json_saida=self.sessao / "testes_resultados" / f"{bloco['name']}_inventario.json",
            workdir=self.sessao / "sim" / f"inventario-{bloco['name']}",
            build_root=self.sessao / "build" / f"componente-{bloco['name']}",
            fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None)
        texto = str((ex.relatorio or {}).get("diagnostico") or ex.saida)
        m = re.search(r"RVGEN_HIERARCHY=(\[.*?\])", texto)
        try:
            caminhos = json.loads(m.group(1)) if m else []
        except (json.JSONDecodeError, AttributeError):
            caminhos = []
        resultado.write_text(json.dumps({"paths": caminhos}, indent=2) + "\n", encoding="utf-8")
        self._log({"evento": "hierarquia_inventariada", "bloco": bloco["name"],
                   "arquivo": resultado.relative_to(self.pasta).as_posix(),
                   "caminhos": len(caminhos), "passou": bool((ex.relatorio or {}).get("passed"))})
        self.relatar(f"  hierarquia {bloco['name']:<15} {len(caminhos)} caminho(s) exposto(s)")
        return caminhos

    def _planejar_diagnostico_interno_cpu(self, bloco: dict, foco: str, evidencia: str,
                                          caminhos: list[str], estado: dict) -> dict | None:
        """O orquestrador escolhe a próxima fronteira interna, nunca sinais inventados."""
        anteriores = estado.get("stages", {})
        observados = [{"id": chave, "status": valor.get("status"),
                       "hypothesis": valor.get("hypothesis"),
                       "paths": valor.get("observation_paths"),
                       "detail": str(valor.get("detail", ""))[-1200:]}
                      for chave, valor in anteriores.items()]
        portas_publicas = {f"dut.{porta.split(':', 1)[0].strip()}"
                           for porta in bloco.get("ports", []) if ':' in porta}
        mensagens = [{"role": "system", "content": self.contrato_testes},
                     {"role": "user", "content": (
                         f"Official regression `{foco}` failed. Choose ONE next diagnostic-only internal "
                         "observation boundary before any new public Cocotb hypothesis. Decide what to "
                         "observe from the listed simulator-inventoried VPI paths based on the official "
                         "evidence and prior observations. Do not choose VHDL, a correction, or a broad "
                         "test. The observation must distinguish one causal boundary (for example decode, "
                         "address, load result, writeback, or register commit), and it must include at "
                         "least one internal VPI path, not merely a declared top-level port. Use only exact "
                         "listed paths. The generated Cocotb test may drive public ports and assert the "
                         "chosen VPI signals, but is diagnostic-only and can never approve conformance.\n\n"
                         f"Official evidence:\n{evidencia[-4000:]}\n\n"
                         f"Available VPI paths:\n{json.dumps(caminhos, ensure_ascii=False)}\n\n"
                         f"Prior internal observations:\n{json.dumps(observados, ensure_ascii=False)}\n\n"
                         "Return only JSON with id, hypothesis, observation_paths, test_plan, and "
                         "failure_meaning.")}]
        self.relatar("  orquestrador diagnóstico: decidindo sinais internos a observar ...")
        for tentativa in (1, 2):
            self.relatar(f"  orquestrador diagnóstico: chamada {tentativa}/2 ...")
            resposta = self._chamar("planejar_diagnostico_interno", foco, mensagens,
                                    schema=_schema_diagnostico_interno(caminhos))
            try:
                plano = extrair_json(resposta.texto)
                identificador = re.sub(r"[^a-z0-9_]+", "_", str(plano.get("id", "")).lower()).strip("_")
                sinais = plano.get("observation_paths")
                internos = [s for s in sinais if s not in portas_publicas] if isinstance(sinais, list) else []
                if (identificador and identificador not in anteriores and isinstance(sinais, list) and
                        sinais and all(s in caminhos for s in sinais) and internos and
                        str(plano.get("hypothesis", "")).strip() and str(plano.get("test_plan", "")).strip() and
                        str(plano.get("failure_meaning", "")).strip()):
                    plano["id"] = identificador
                    plano["observation_paths"] = sinais
                    return plano
            except (ErroLLM, AttributeError, TypeError):
                pass
            mensagens += [{"role": "assistant", "content": resposta.texto},
                          {"role": "user", "content":
                           "Return a distinct valid observation using at least one exact internal VPI path."}]
        return None

    def _diagnosticar_falha_oficial_na_cpu(self, bloco: dict, arq: dict,
                                            foco: str, evidencia: str) -> tuple[bool, str, bool]:
        """Explora uma etapa causal VPI por vez; nunca aprova a CPU."""
        inventario = self.sessao / "hierarquia" / f"{bloco['name']}.json"
        if not inventario.exists():
            self.relatar("  diagnóstico interno CPU: inventariando sinais VPI ...")
            self._inventariar_hierarquia(bloco, arq)
        try:
            caminhos = json.loads(inventario.read_text(encoding="utf-8")).get("paths", [])
        except (OSError, ValueError, json.JSONDecodeError):
            caminhos = []
        nome = re.sub(r"[^a-z0-9_]+", "_", foco.lower()).strip("_")
        estado_path = self.sessao / "diagnosticos_internos" / f"estado_cpu_{nome}.json"
        fonte_hash = hashlib.sha256(self._ler(bloco["file"]).encode("utf-8")).hexdigest()
        try:
            estado = json.loads(estado_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            estado = {}
        if estado.get("fonte_hash") != fonte_hash:
            estado = {"fonte_hash": fonte_hash, "stages": {}, "diagnostic_runs": 0}
        falha = next(((chave, dado) for chave, dado in estado["stages"].items()
                       if dado.get("status") == "failed"), None)
        if falha:
            dado = estado["stages"][falha[0]]
            return True, (f"Internal CPU diagnostic isolated failing stage `{falha[0]}`: "
                           f"{dado.get('detail', '')}"), False
        if len(estado["stages"]) >= 5:
            return False, ("Five orchestrator-selected internal observation boundaries completed "
                           "without isolating a failing signal; continue with public causal exploration."), True
        pendente = estado.get("pending_testbench")
        if isinstance(pendente, dict) and isinstance(pendente.get("plan"), dict):
            plano_diagnostico = pendente["plan"]
            tentativa_pendente = min(int(pendente.get("attempts", 0)) + 1, 3)
            self.relatar(f"  diagnóstico interno CPU: etapa {plano_diagnostico.get('id')} — "
                         f"corrigindo testbench ({tentativa_pendente}/3; mesma verificação) ...")
        else:
            plano_diagnostico = self._planejar_diagnostico_interno_cpu(
                bloco, foco, evidencia, caminhos, estado)
        if plano_diagnostico is None:
            return False, ("The orchestrator could not select a valid internal VPI observation from "
                           "the simulator inventory."), True
        etapa = plano_diagnostico["id"]
        destino = self.sessao / "diagnosticos_internos" / f"test_cpu_{nome}_{etapa}.py"
        if not destino.exists():
            plano = (f"Behavior: verify ONLY this orchestrator-selected causal boundary behind official `{foco}`.\n"
                     f"Hypothesis: {plano_diagnostico['hypothesis']}\n"
                     f"Evidence: {evidencia[:3000]}\n"
                     f"Internal observations (exact inventoried paths): {json.dumps(plano_diagnostico['observation_paths'])}\n"
                     f"Discriminating test: {plano_diagnostico['test_plan']}\n"
                     f"Failure meaning: {plano_diagnostico['failure_meaning']}\n"
                     "Stimulus: smallest legal RV32I public-port scenario that reaches this boundary.\n"
                     "Assert only the listed internal signals needed for this one boundary.\n"
                     "Forbidden: VHDL changes, unconfirmed paths, or normative approval.")
            if pendente:
                self.relatar(f"  diagnóstico interno CPU: etapa {etapa} — "
                             "materializando correção do testbench ...")
            else:
                self.relatar(f"  diagnóstico interno CPU: gerando etapa {etapa} para {foco} ...")
            rejeicoes = estado.setdefault("testbench_rejections", {})
            anterior = str(rejeicoes.get(etapa, {}).get("detail", ""))
            if anterior:
                plano += ("\nPrevious testbench candidates were rejected. Correct this exact issue "
                          f"without changing the diagnostic stage:\n{anterior[-5000:]}")
            try:
                self._escrever_caso_interno_isolado(bloco, destino, plano, caminhos,
                                                     self._caminho_teste(bloco))
            except ErroPlanoTeste as erro:
                tentativa = int(rejeicoes.get(etapa, {}).get("attempts", 0)) + 1
                rejeicoes[etapa] = {"attempts": tentativa, "detail": str(erro)[-5000:]}
                estado["pending_testbench"] = {"plan": plano_diagnostico,
                                                "attempts": tentativa,
                                                "detail": str(erro)[-5000:]}
                if tentativa >= 3:
                    estado["stages"][etapa] = {
                        "status": "unavailable", "detail": str(erro)[-5000:],
                        "hypothesis": plano_diagnostico["hypothesis"],
                        "observation_paths": plano_diagnostico["observation_paths"]}
                    estado.pop("pending_testbench", None)
                estado_path.parent.mkdir(parents=True, exist_ok=True)
                estado_path.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
                self._log({"evento": "diagnostico_cpu_testbench_rejeitado", "foco": foco,
                           "etapa": etapa, "tentativa": tentativa,
                           "status": "unavailable" if tentativa >= 3 else "invalid",
                           "motivo": str(erro)[-5000:]})
                self.relatar(f"  diagnóstico interno CPU: etapa {etapa} — testbench rejeitado "
                             f"({tentativa}/3; mesma verificação)")
                return False, (f"Internal CPU diagnostic testbench for `{etapa}` was rejected; "
                               f"hardware was not judged:\n{erro}"), False
        self.relatar(f"  diagnóstico interno CPU: executando etapa {etapa} ...")
        vcd = self.sessao / "vcd" / f"{nome}_{etapa}.vcd"
        self.relatar(f"  diagnóstico interno CPU: gravando VCD em {vcd.name} ...")
        ex = self.executor.rodar_componente(
            self.pasta, componente=bloco["name"], teste=destino,
            json_saida=self.sessao / "testes_resultados" / f"diagnostico-{nome}.json",
            workdir=self.sessao / "sim" / f"diagnostico-{nome}",
            build_root=self.sessao / "build" / f"diagnostico-{nome}",
            fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None,
            vcd=vcd)
        rel = ex.relatorio or {}
        passou = bool(rel.get("passed"))
        detalhe = str(rel.get("diagnostico") or rel.get("detail") or ex.saida)[-4000:]
        status = "confirmed" if passou else ("failed" if _falha_de_assertion(ex) else "invalid")
        if status == "invalid":
            self.relatar("  diagnóstico interno CPU: erro Python/Cocotb; corrigindo testbench ...")
            try:
                self._corrigir_testbench(
                    bloco, destino, detalhe,
                    tabela_falhas_cocotb(
                        detalhe, destino.read_text(encoding="utf-8", errors="replace")))
                self.relatar("  diagnóstico interno CPU: candidato Cocotb corrigido; reexecutando ...")
                ex = self.executor.rodar_componente(
                    self.pasta, componente=bloco["name"], teste=destino,
                    json_saida=self.sessao / "testes_resultados" / f"diagnostico-{nome}.json",
                    workdir=self.sessao / "sim" / f"diagnostico-{nome}",
                    build_root=self.sessao / "build" / f"diagnostico-{nome}",
                    fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None,
                    vcd=vcd)
                rel = ex.relatorio or {}
                passou = bool(rel.get("passed"))
                detalhe = str(rel.get("diagnostico") or rel.get("detail") or ex.saida)[-4000:]
                status = "confirmed" if passou else ("failed" if _falha_de_assertion(ex) else "invalid")
            except ErroPlanoTeste as erro:
                detalhe = f"Testbench correction rejected: {erro}"
        if status == "invalid":
            rejeicoes = estado.setdefault("testbench_rejections", {})
            tentativa = int(rejeicoes.get(etapa, {}).get("attempts", 0)) + 1
            rejeicoes[etapa] = {"attempts": tentativa, "detail": detalhe[-5000:]}
            estado["pending_testbench"] = {"plan": plano_diagnostico,
                                            "attempts": tentativa, "detail": detalhe[-5000:]}
            if tentativa < 3:
                estado_path.parent.mkdir(parents=True, exist_ok=True)
                estado_path.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n",
                                       encoding="utf-8")
                self.relatar(f"  diagnóstico interno CPU: etapa {etapa} — testbench ainda inválido "
                             f"({tentativa}/3; mesma verificação)")
                return False, (f"Internal CPU diagnostic testbench for `{etapa}` failed before "
                               f"a DUT assertion; hardware was not judged:\n{detalhe}"), False
            status = "unavailable"
            estado.pop("pending_testbench", None)
        resumo: dict | None = None
        revisao: dict | None = None
        if vcd.exists():
            resumo = self._resumir_vcd(vcd, destino, bloco, detalhe)
            resumo_path = vcd.with_suffix(".summary.json")
            resumo_path.write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n",
                                   encoding="utf-8")
        if status in {"confirmed", "failed"}:
            plano_revisao = {
                "file": bloco["file"],
                "hypothesis": plano_diagnostico["hypothesis"],
                "evidence": [foco, *plano_diagnostico["observation_paths"]],
                "failure_meaning": plano_diagnostico["failure_meaning"],
                "pass_meaning": ("The selected internal boundary agrees with its expected "
                                 "value for this diagnostic stimulus."),
            }
            self.relatar(f"  diagnóstico interno CPU: revisando VCD da etapa {etapa} ...")
            revisao = self._revisar_hipotese_exploratoria(
                plano_revisao, destino, detalhe, resumo)
            if not revisao["diagnostic_test_valid"]:
                status = "inconclusive"
            elif passou:
                status = "confirmed" if revisao["verdict"] == "refuted" else "inconclusive"
            else:
                status = "failed" if revisao["verdict"] == "confirmed" else "inconclusive"
            self.relatar(f"  diagnóstico interno CPU: revisão VCD {status.upper()} — "
                         f"{self._linha_curta(revisao.get('rationale'))}")
        estado["stages"][etapa] = {"status": status, "detail": detalhe,
                                    "test": destino.relative_to(self.pasta).as_posix(),
                                    "hypothesis": plano_diagnostico["hypothesis"],
                                    "observation_paths": plano_diagnostico["observation_paths"],
                                    "failure_meaning": plano_diagnostico["failure_meaning"]}
        estado.pop("pending_testbench", None)
        estado["diagnostic_runs"] = int(estado.get("diagnostic_runs", 0)) + 1
        if vcd and vcd.exists():
            estado["stages"][etapa]["vcd"] = vcd.relative_to(self.pasta).as_posix()
        if resumo is not None:
            estado["stages"][etapa]["vcd_summary"] = resumo_path.relative_to(self.pasta).as_posix()
        if revisao is not None:
            estado["stages"][etapa]["review"] = revisao
        estado_path.parent.mkdir(parents=True, exist_ok=True)
        estado_path.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._log({"evento": "diagnostico_oficial_interno_cpu", "foco": foco, "etapa": etapa,
                   "arquivo": destino.relative_to(self.pasta).as_posix(), "passou": passou,
                   "vcd": vcd.relative_to(self.pasta).as_posix() if vcd and vcd.exists() else None,
                   "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
        return status == "failed", (f"Internal CPU diagnostic stage `{etapa}` {status} "
                                     f"(diagnostic-only):\n{detalhe}"), False

    def _estado_exploracao_cpu(self, foco: str, cpu: dict) -> tuple[Path, dict]:
        """Estado por falha/hash que impede repetir hipóteses já refutadas."""
        nome = re.sub(r"[^a-z0-9_]+", "_", foco.lower()).strip("_")
        caminho = self.sessao / "exploracoes_cpu" / f"{nome}.json"
        fonte_hash = hashlib.sha256(self._ler(cpu["file"]).encode("utf-8")).hexdigest()
        try:
            estado = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            estado = {}
        if estado.get("fonte_hash") != fonte_hash:
            estado = {"foco": foco, "fonte_hash": fonte_hash, "bloqueados": {},
                      "concluidos": {}, "ativado": False}
        return caminho, estado

    def _capturar_execucao_oficial_focal(self, cpu: dict, foco: str, estado_path: Path,
                                         estado: dict) -> dict:
        """Executa o ELF oficial focal em Cocotb, com VCD e traço público completo."""
        nome = re.sub(r"[^a-z0-9_]+", "_", foco.lower()).strip("_")
        destino = self.sessao / "tracos_oficiais" / nome
        atual = estado.get("official_execution")
        if isinstance(atual, dict):
            vcd = self.pasta / str(atual.get("vcd", ""))
            trace = self.pasta / str(atual.get("trace", ""))
            if vcd.exists() and trace.exists():
                return atual
        self.relatar(f"  execução oficial focal: Cocotb + VCD + traço completo para {foco} ...")
        ex = self.executor.rodar(
            self.pasta, json_saida=destino / "report.json",
            workdir=self.sessao / "sim" / f"oficial-{nome}",
            build_root=self.sessao / "build" / f"oficial-{nome}",
            casos=[foco], etapa=self.isa, ondas=True, traco_completo=True)
        resultado = next((item for item in (ex.relatorio or {}).get("results", [])
                          if item.get("test") == foco), {})
        vcd_bruto = str(resultado.get("vcd", "")).strip()
        trace_bruto = str(resultado.get("trace_file", "")).strip()
        vcd = Path(vcd_bruto) if vcd_bruto else None
        trace = Path(trace_bruto) if trace_bruto else None
        dados = {"report": ex.json_path.relative_to(self.pasta).as_posix(),
                 "vcd": vcd.relative_to(self.pasta).as_posix() if vcd and vcd.exists() else "",
                 "trace": trace.relative_to(self.pasta).as_posix() if trace and trace.exists() else "",
                 "cycle": resultado.get("cycle"), "pc": resultado.get("pc"),
                 "tohost": resultado.get("tohost"), "test_case": resultado.get("test_case")}
        estado["official_execution"] = dados
        self._salvar_estado_exploracao_cpu(estado_path, estado)
        self._log({"evento": "execucao_oficial_vcd", "foco": foco, **dados})
        self.relatar(f"  execução oficial focal: VCD e traço salvos ({dados['cycle']} ciclo(s))")
        return dados

    def _salvar_estado_exploracao_cpu(self, caminho: Path, estado: dict) -> None:
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(json.dumps(estado, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    def _registrar_reproducao_publica_do_diagnostico(self, foco: str, estado: dict,
                                                      status: str, teste: Path) -> None:
        """Fecha uma fronteira VPI somente após sua reprodução pública."""
        etapa = estado.get("internal_diagnostic_stage")
        if not etapa or status not in {"refuted", "confirmed"}:
            return
        nome = re.sub(r"[^a-z0-9_]+", "_", foco.lower()).strip("_")
        caminho = self.sessao / "diagnosticos_internos" / f"estado_cpu_{nome}.json"
        try:
            diagnostico = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            return
        dado = diagnostico.get("stages", {}).get(etapa)
        if not isinstance(dado, dict):
            return
        dado["public_reproduction"] = {
            "status": status,
            "test": teste.relative_to(self.pasta).as_posix(),
        }
        if status == "refuted":
            # A divergência VPI não sobreviveu às portas públicas: não a use
            # novamente como causa e devolva a decisão ao orquestrador.
            dado["status"] = "public_refuted"
            estado.pop("internal_diagnostic_finding", None)
            estado.pop("internal_diagnostic_stage", None)
        caminho.write_text(json.dumps(diagnostico, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")

    def _bloquear_hipotese_focal(self, foco: str, cpu: dict, alvo: str, motivo: str) -> None:
        caminho, estado = self._estado_exploracao_cpu(foco, cpu)
        estado["bloqueados"][alvo] = motivo
        estado["ativado"] = True
        self._salvar_estado_exploracao_cpu(caminho, estado)
        self._log({"evento": "hipotese_focal_bloqueada", "foco": foco, "arquivo": alvo,
                   "motivo": motivo})

    def _evidencia_exploratoria_compacta(self, estado: dict) -> str:
        """Entrega resultados e amostras VCD, nunca o traço bruto, ao planejador."""
        itens = []
        for nome, dado in estado.get("concluidos", {}).items():
            item: dict[str, Any] = {
                "test": nome, "status": dado.get("status"),
                "detail_tail": str(dado.get("detail", ""))[-1200:],
            }
            resumo_rel = dado.get("vcd_summary")
            if resumo_rel:
                try:
                    resumo = json.loads((self.pasta / resumo_rel).read_text(encoding="utf-8"))
                    item["vcd"] = {chave: resumo.get(chave) for chave in
                                   ("failure_time_ns", "selected", "missing", "samples")}
                except (OSError, ValueError, json.JSONDecodeError):
                    item["vcd"] = {"error": "summary unavailable"}
            itens.append(item)
        hipoteses = []
        for item in estado.get("hypotheses", []):
            compacto = {chave: item.get(chave) for chave in
                        ("file", "hypothesis", "evidence", "status", "result_detail", "review")}
            resumo_rel = item.get("vcd_summary")
            if resumo_rel:
                try:
                    resumo = json.loads((self.pasta / resumo_rel).read_text(encoding="utf-8"))
                    compacto["vcd"] = {chave: resumo.get(chave) for chave in
                                      ("failure_time_ns", "selected", "missing", "samples")}
                except (OSError, ValueError, json.JSONDecodeError):
                    compacto["vcd"] = {"error": "summary unavailable"}
            hipoteses.append(compacto)
        oficial = dict(estado.get("official_execution") or {})
        trace = self.pasta / str(oficial.get("trace", ""))
        vcd = self.pasta / str(oficial.get("vcd", ""))
        if trace.exists():
            try:
                oficial["public_events"] = json.loads(trace.read_text(encoding="utf-8")).get("events", [])
            except (OSError, ValueError, json.JSONDecodeError):
                oficial["public_events"] = "trace unavailable"
        if vcd.exists():
            # O caso oficial focal é curto; entregue o VCD completo para uma
            # revisão auditável, acompanhado do JSON por evento acima.
            oficial["vcd_raw"] = vcd.read_text(encoding="utf-8", errors="replace")
        return json.dumps({"observations": itens, "previous_hypotheses": hipoteses,
                            "official_execution": oficial,
                            "internal_diagnostic_finding": estado.get("internal_diagnostic_finding")},
                          ensure_ascii=False, indent=2)

    def _ancora_execucao_oficial(self, estado: dict) -> dict | None:
        """Extrai load → resposta → consumidor do traço do ELF oficial."""
        oficial = estado.get("official_execution") or {}
        trace = self.pasta / str(oficial.get("trace", ""))
        try:
            eventos = json.loads(trace.read_text(encoding="utf-8")).get("events", [])
        except (OSError, ValueError, json.JSONDecodeError):
            return None
        for indice in range(len(eventos) - 1, -1, -1):
            carga = eventos[indice]
            if not str(carga.get("decoded", "")).startswith("load("):
                continue
            resposta = eventos[indice + 1] if indice + 1 < len(eventos) else None
            consumidor = next((evento for evento in eventos[indice + 1:indice + 4]
                               if str(evento.get("decoded", "")).startswith(
                               ("branch(", "op-imm(", "op x", "store("))), None)
            if resposta and consumidor:
                return {"load_cycle": carga.get("cycle"), "load_pc": carga.get("pc"),
                        "load_instruction": carga.get("instruction"),
                        "response_cycle": resposta.get("cycle"),
                        "data_address": resposta.get("data_addr"),
                        "data_word": resposta.get("data_read_data"),
                        "consumer_cycle": consumidor.get("cycle"),
                        "consumer_pc": consumidor.get("pc"),
                        "consumer_instruction": consumidor.get("instruction"),
                        "consumer_decoded": consumidor.get("decoded")}
        return None

    def _planejar_hipotese_exploratoria(self, cpu: dict, arq: dict, foco: str,
                                        evidencia: str, estado: dict) -> dict | None:
        """Formula uma hipótese falsificável; não solicita nem aceita VHDL."""
        arquivos = [bloco["file"] for bloco in arq["blocks"]]
        fontes = "\n\n".join(
            f"### {arquivo}\n```vhdl\n{self._ler(arquivo)}\n```" for arquivo in arquivos)
        observacoes = self._evidencia_exploratoria_compacta(estado)
        ancora = self._ancora_execucao_oficial(estado)
        mensagens = [{"role": "system", "content": self.contrato_testes},
                     {"role": "user", "content": (
                         f"Investigate official failure `{foco}` without changing VHDL. Analyze the "
                         "completed Cocotb observations and bounded VCD samples, then propose ONE new "
                         "minimal discriminating Cocotb experiment for ONE causal hypothesis. The test "
                          "must distinguish that hypothesis from alternatives at a precise boundary. Do "
                          "not repeat a previous hypothesis or broad ISA regression. A failing assertion "
                         "must have the exact causal meaning described in `failure_meaning`; a passing "
                         "test must refute or narrow it as described in `pass_meaning`. The previous "
                          "test review and VCD, when present, are authoritative inputs for deciding the "
                          "next hypothesis. If `internal_diagnostic_finding` is present, the next public "
                          "test must reproduce or refute that exact boundary through declared ports before "
                          "any VHDL correction is considered. Do not derive the experiment from generic "
                          "test ideas or a prior review's suggested next test.\n\n"
                          + (f"MANDATORY OFFICIAL ANCHOR (copy it unchanged into `official_anchor`; "
                             "the test must preserve this load response and immediate consumer, not "
                             f"substitute another byte lane/value):\n{json.dumps(ancora, ensure_ascii=False)}\n\n"
                             if ancora else "") +
                          f"Official evidence:\n{evidencia[-4000:]}\n\n"
                          f"Observations, official full trace and official raw VCD:\n{observacoes}\n\n"
                         f"Current VHDL sources (inspection only):\n{fontes}\n\n"
                         "Return only the requested JSON with exactly these top-level keys: `file`, "
                         "`hypothesis`, `evidence`, `test_plan`, `failure_meaning`, and `pass_meaning`. "
                         "Do not return VHDL, Python, encoded instruction words, or a nested `experiment` "
                         "object; assembly programs must be described with mnemonics and labels.")}]
        anteriores = {hashlib.sha256((str(item.get("file")) + "\n" +
                                      str(item.get("hypothesis"))).lower().encode()).hexdigest()
                      for item in estado.get("hypotheses", [])}
        self.relatar("  orquestrador adaptativo: analisando evidência oficial, histórico e VCD "
                     "para definir a próxima hipótese ...")
        for tentativa in (1, 2):
            self.relatar(f"  orquestrador adaptativo: chamada {tentativa}/2 ...")
            resposta = self._chamar("hipotese_exploratoria", foco, mensagens,
                                    schema=_schema_hipotese_exploratoria(arquivos, ancora))
            try:
                plano = extrair_json(resposta.texto)
                # Alguns provedores tratam JSON schema apenas como orientação
                # e retornam um experimento aninhado. Preserve a hipótese útil,
                # mas remova encodings e normalize para o contrato interno.
                if not plano.get("test_plan") and isinstance(plano.get("experiment"), dict):
                    experimento = dict(plano["experiment"])
                    experimento.pop("program_words", None)
                    programa = experimento.get("program_meaning")
                    if programa:
                        experimento["assembly_requirement"] = (
                            "Materialize program_meaning with assemble_rv32i; never use encoded words.")
                    fronteira = str(plano.get("boundary", "")).strip()
                    plano["test_plan"] = json.dumps(
                        {"experiment": experimento, "boundary": fronteira}, ensure_ascii=False)
                    evidencia_bruta = plano.get("evidence")
                    plano["evidence"] = (evidencia_bruta if isinstance(evidencia_bruta, list) else
                                         [str(evidencia_bruta)] if evidencia_bruta else
                                         [fronteira or str(plano.get("hypothesis", ""))])
                if plano.get("file") not in arquivos:
                    plano["file"] = cpu["file"]
                    plano["target_pending"] = True
                assinatura = hashlib.sha256((str(plano.get("file")) + "\n" +
                                              str(plano.get("hypothesis"))).lower().encode()).hexdigest()
                texto_plano = json.dumps(plano, ensure_ascii=False).lower()
                ancora_valida = not ancora or all(
                    str(valor).lower() in texto_plano for valor in (
                        ancora["data_address"], ancora["data_word"],
                        "bne", ancora["consumer_instruction"]))
                if (plano.get("file") in arquivos and str(plano.get("hypothesis", "")).strip() and
                        str(plano.get("test_plan", "")).strip() and assinatura not in anteriores and
                        ancora_valida):
                    plano["official_anchor"] = ancora
                    plano["signature"] = assinatura
                    self.relatar("  orquestrador adaptativo: próximo experimento definido")
                    return plano
            except (ErroLLM, AttributeError, TypeError):
                pass
            mensagens += [{"role": "assistant", "content": resposta.texto},
                          {"role": "user", "content":
                            "The hypothesis was invalid, duplicated, or did not preserve the mandatory "
                            "official anchor. Return one distinct falsifiable plan that explicitly cites "
                            "the official load response address/word and its immediate BNE consumer."}]
            self.relatar("  orquestrador adaptativo: resposta inválida ou duplicada; "
                         "solicitando novo plano")
        self.relatar("  orquestrador adaptativo: nenhuma próxima hipótese válida foi definida")
        return None

    @staticmethod
    def _hipoteses_que_contam(hipoteses: list[dict]) -> int:
        """Conta somente hipóteses causais realmente revisadas, não erros Cocotb."""
        return sum(1 for item in hipoteses
                   if item.get("status") in {"confirmed", "refuted", "inconclusive"} and
                   bool((item.get("review") or {}).get("diagnostic_test_valid")))

    @staticmethod
    def _normalizar_revisao_hipotese(bruta: dict) -> dict:
        """Aceita o schema canônico e o formato descritivo comum dos provedores."""
        def texto(valor: Any) -> str:
            if isinstance(valor, dict):
                return str(valor.get("reason") or valor.get("interpretation") or
                           valor.get("impact") or valor.get("verdict") or "")
            return str(valor or "")

        observacoes = bruta.get("evidence")
        if not isinstance(observacoes, list):
            observacoes = bruta.get("observations") or bruta.get("concrete_observations") or []
            if not isinstance(observacoes, list):
                observacoes = []
            for item in bruta.get("waveform_observations") or []:
                if isinstance(item, dict):
                    tempo = item.get("time_ns")
                    observacao = str(item.get("observation", "")).strip()
                    observacoes.append(f"{tempo} ns: {observacao}" if tempo is not None else observacao)
                elif str(item).strip():
                    observacoes.append(str(item).strip())
        observacoes = [texto(item) for item in observacoes if texto(item)]
        while len(observacoes) < 2:
            complemento = (bruta.get("assertion_assessment") or
                           bruta.get("hypothesis_assessment") or
                           bruta.get("reason") or "insufficient review evidence")
            observacoes.append(texto(complemento))

        validade = bruta.get("diagnostic_test_valid")
        if not isinstance(validade, bool):
            validade = bruta.get("test_is_valid")
        if not isinstance(validade, bool):
            semantica_bruta = bruta.get("semantic_validity", bruta.get("semantic_valid"))
            semantica = texto(semantica_bruta).lower()
            razao = texto(bruta.get("reason") or semantica_bruta).lower()
            # Probes VPI inventariados são válidos para diagnóstico, embora
            # nunca possam aprovar normativamente a CPU.
            somente_interno = ("internal" in razao or "vpi" in razao) and not any(
                termo in razao for termo in ("does not exist", "unconfirmed", "uninventoried",
                                             "attributeerror", "syntax", "import"))
            validade = semantica in {"valid", "diagnostic-valid", "diagnostic-valid-only"} or somente_interno

        normativa = bruta.get("normative_approval_allowed")
        if not isinstance(normativa, bool):
            semantica_bruta = bruta.get("semantic_validity", bruta.get("semantic_valid"))
            if isinstance(semantica_bruta, dict) and isinstance(semantica_bruta.get("normative_approval"), bool):
                normativa = semantica_bruta["normative_approval"]
            else:
                razao = texto(bruta.get("reason") or semantica_bruta).lower()
                normativa = bool(validade) and "internal" not in razao and "vpi" not in razao

        veredito = str(bruta.get("verdict", "")).lower()
        if veredito not in {"confirmed", "refuted", "inconclusive"}:
            decisao = texto(bruta.get("decision", "")).lower()
            avaliacao_bruta = bruta.get("hypothesis_assessment", bruta.get("hypothesis_confirmation"))
            avaliacao = texto(avaliacao_bruta).lower()
            if isinstance(avaliacao_bruta, dict):
                veredito = str(avaliacao_bruta.get("verdict", "")).lower()
            if decisao in {"confirm", "confirmed", "accept"}:
                veredito = "confirmed"
            elif decisao in {"refute", "refuted"} or "refute" in avaliacao:
                veredito = "refuted"
            elif veredito not in {"confirmed", "refuted", "inconclusive"}:
                veredito = "inconclusive"

        proximo = bruta.get("next_test") or bruta.get("recommended_discriminating_plan")
        if isinstance(proximo, dict):
            plano_proximo = texto(proximo.get("discriminating_plan") or proximo.get("test"))
            if isinstance(proximo.get("discriminating_plan"), list):
                plano_proximo = " ".join(map(str, proximo["discriminating_plan"]))
            hipotese_proxima = str(proximo.get("hypothesis") or bruta.get("next_hypothesis") or "")
        else:
            plano_proximo = texto(bruta.get("next_test_plan") or proximo)
            hipotese_proxima = str(bruta.get("next_hypothesis") or "")
        decisao_vcd = bruta.get("vcd_decision")
        precisa = bruta.get("next_test_needed")
        if not isinstance(precisa, bool):
            precisa = bruta.get("another_test_needed", bruta.get("another_test_necessary"))
        if not isinstance(precisa, bool) and isinstance(decisao_vcd, dict):
            precisa = decisao_vcd.get("another_test_necessary")
        if not isinstance(precisa, bool):
            precisa = bool(plano_proximo or hipotese_proxima)

        return {
            "verdict": veredito,
            "rationale": texto(bruta.get("rationale") or bruta.get("reason") or
                                bruta.get("hypothesis_assessment") or
                                bruta.get("hypothesis_confirmation") or "").strip(),
            "evidence": observacoes,
            "diagnostic_test_valid": bool(validade),
            "normative_approval_allowed": bool(normativa),
            "next_test_needed": precisa,
            "next_hypothesis": hipotese_proxima,
            "next_test_plan": plano_proximo,
        }

    def _revisar_hipotese_exploratoria(self, plano: dict, teste: Path,
                                       detalhe: str, resumo: dict | None) -> dict:
        """Revisa teste e VCD antes de permitir que a evidência toque VHDL."""
        alvo = str(plano["file"])
        mensagens = [{"role": "system", "content": self.contrato_testes},
                     {"role": "user", "content": (
                         "Review a causal Cocotb experiment after execution. Do not propose or emit "
                         "VHDL. Decide whether the test is semantically valid and whether its assertion "
                         "plus bounded VCD samples directly confirm the stated hypothesis. Reject test "
                         "assumption errors, timing/modeling artifacts, unrelated assertions, missing "
                         "signals, and ambiguous evidence as `inconclusive`. A simulator assertion alone "
                         "is not sufficient. Simulator-inventoried internal VPI probes ARE allowed for "
                         "causal diagnosis; mark such a test diagnostic-valid while keeping normative "
                         "approval false. Only public ports and the official suite can approve the CPU. "
                          "Cite at least two concrete observations. Do not recommend a next test or a "
                          "different hypothesis: the orchestrator selects the next internal observation "
                          "from the simulator inventory.\n\n"
                         f"Suspected file: {alvo}\nHypothesis: {plano['hypothesis']}\n"
                         f"Failure meaning: {plano['failure_meaning']}\n"
                         f"Pass meaning: {plano['pass_meaning']}\n\n"
                         f"Complete testbench:\n```python\n"
                         f"{teste.read_text(encoding='utf-8', errors='replace')}\n```\n\n"
                         f"Execution detail:\n{detalhe[-5000:]}\n\n"
                         f"VCD summary (diagnostic-only):\n"
                         f"{json.dumps(resumo or {'missing': 'no summary'}, ensure_ascii=False)[:12000]}\n\n"
                         f"Current suspected source:\n```vhdl\n{self._ler(alvo)}\n```\n\n"
                         "Return only the requested JSON.")}]
        try:
            self.relatar("  revisor causal: analisando semântica do teste e amostras VCD ...")
            resposta = self._chamar("revisao_hipotese", alvo, mensagens,
                                    schema=_SCHEMA_REVISAO_HIPOTESE)
            revisao = self._normalizar_revisao_hipotese(extrair_json(resposta.texto))
            if (revisao.get("verdict") in {"confirmed", "refuted", "inconclusive"} and
                    isinstance(revisao.get("diagnostic_test_valid"), bool) and
                    len(revisao.get("evidence") or []) >= 2):
                if not revisao["diagnostic_test_valid"]:
                    revisao["verdict"] = "inconclusive"
                return revisao
        except (ErroLLM, AttributeError, TypeError):
            pass
        return {"verdict": "inconclusive", "diagnostic_test_valid": False,
                "normative_approval_allowed": False,
                "rationale": "structured causal review was unavailable",
                "evidence": ["no valid review", "VHDL change blocked"]}

    def _explorar_cpu_superior(self, cpu: dict, arq: dict, foco: str,
                                evidencia: str) -> tuple[bool, bool, str, str | None]:
        """Cria observações; só teste causal dedicado autoriza uma correção."""
        caminho, estado = self._estado_exploracao_cpu(foco, cpu)
        self._ultima_exploracao_falha = None
        if not estado.get("ativado"):
            return False, False, "", None
        # A reprodução pública é o portão primário para uma correção candidata.
        # Instrumentação interna é reservada para quando essa reprodução não
        # puder ser materializada de forma válida.
        pendente = None
        if pendente is None:
            if estado.get("analysis_complete"):
                return False, True, str(estado.get(
                    "analysis_conclusion", "Causal analysis concluded without an authorized change.")), None
            hipoteses = estado.setdefault("hypotheses", [])
            ativa = next((item for item in hipoteses
                          if item.get("status") in {"planned", "invalid"}), None)
            if ativa is None:
                if any(item.get("status") == "unavailable" for item in hipoteses):
                    return False, True, ("The public reproduction testbench could not be made "
                                         "valid after three corrections."), None
                if self._hipoteses_que_contam(hipoteses) >= 1:
                    return False, True, ("The single public reproduction did not authorize a "
                                         "VHDL correction."), None
                ativa = self._planejar_hipotese_exploratoria(cpu, arq, foco, evidencia, estado)
                if ativa is None:
                    return False, True, ("No new non-duplicated causal hypothesis could be planned; "
                                         "no VHDL change was authorized."), None
                ativa["status"] = "planned"
                ativa["attempts"] = 0
                hipoteses.append(ativa)
                self._salvar_estado_exploracao_cpu(caminho, estado)
            indice = hipoteses.index(ativa) + 1
            nome_hipotese = f"hypothesis_{indice:02d}"
            alvo_resumo = ("a localizar após confirmação" if ativa.get("target_pending") else
                           str(ativa.get("file", "não informado")))
            self.relatar(f"  reprodução pública {indice}/1: {self._linha_curta(ativa.get('hypothesis'))}")
            self.relatar(f"    alvo provisório: {alvo_resumo}")
            self.relatar(f"    teste proposto: {self._linha_curta(ativa.get('test_plan'))}")
            self.relatar(f"    se falhar: {self._linha_curta(ativa.get('failure_meaning'))}")
            destino = self.sessao / "exploracoes_cpu" / (
                f"test_{re.sub(r'[^a-z0-9_]+', '_', foco.lower()).strip('_')}_{nome_hipotese}.py")
            plano_hipotese = (
                f"Causal hypothesis: {ativa['hypothesis']}\n"
                f"Suspected file: {ativa['file']}\n"
                f"Evidence: {json.dumps(ativa.get('evidence', []), ensure_ascii=False)}\n"
                f"Discriminating experiment: {ativa['test_plan']}\n"
                f"Meaning if assertion fails: {ativa['failure_meaning']}\n"
                f"Meaning if test passes: {ativa['pass_meaning']}\n"
                "Create only this causal experiment. Its focal assertion must distinguish the stated "
                "hypothesis; do not modify VHDL or broaden ISA coverage.")
            if not destino.exists():
                inventario = self.sessao / "hierarquia" / f"{cpu['name']}.json"
                try:
                    caminhos = json.loads(inventario.read_text(encoding="utf-8")).get("paths", [])
                except (OSError, ValueError, json.JSONDecodeError):
                    caminhos = self._inventariar_hierarquia(cpu, arq)
                try:
                    self.relatar("  gerador Cocotb: materializando teste de reprodução pública ...")
                    self._escrever_caso_interno_isolado(cpu, destino, plano_hipotese, caminhos,
                                                         self._caminho_teste(cpu))
                except ErroPlanoTeste as erro:
                    ativa["attempts"] = int(ativa.get("attempts", 0)) + 1
                    ativa["status"] = "unavailable" if ativa["attempts"] >= 3 else "invalid"
                    ativa["result_detail"] = str(erro)[-5000:]
                    self._salvar_estado_exploracao_cpu(caminho, estado)
                    return False, False, (f"Causal hypothesis testbench rejected "
                                           f"({ativa['attempts']}/3):\n{erro}"), None
            vcd_hipotese = self.sessao / "vcd" / (
                f"{re.sub(r'[^a-z0-9_]+', '_', foco.lower()).strip('_')}_{nome_hipotese}.vcd")
            self.relatar("  executor Cocotb: executando reprodução pública com VCD ...")
            ex_hipotese = self.executor.rodar_componente(
                self.pasta, componente=cpu["name"], teste=destino,
                json_saida=self.sessao / "testes_resultados" / f"{nome_hipotese}.json",
                workdir=self.sessao / "sim" / nome_hipotese,
                build_root=self.sessao / "build" / nome_hipotese,
                fontes=self._fontes_do_bloco(cpu, arq) if self.gates_componentes else None,
                vcd=vcd_hipotese)
            resultado_runtime = ("passed" if bool((ex_hipotese.relatorio or {}).get("passed")) else
                                 "assertion_failed" if _falha_de_assertion(ex_hipotese) else
                                 "invalid")
            self.relatar("  reprodução pública: resultado da simulação = "
                          f"{resultado_runtime}")
            status_hipotese = ("refuted" if resultado_runtime == "passed" else
                               "confirmed" if resultado_runtime == "assertion_failed" else "invalid")
            detalhe_hipotese = str((ex_hipotese.relatorio or {}).get("diagnostico") or
                                    ex_hipotese.saida)[-5000:]
            if status_hipotese == "invalid":
                try:
                    self._corrigir_testbench(
                        cpu, destino, detalhe_hipotese,
                        tabela_falhas_cocotb(
                            detalhe_hipotese, destino.read_text(encoding="utf-8", errors="replace")))
                except ErroPlanoTeste as erro:
                    detalhe_hipotese = f"Testbench correction rejected: {erro}"
                ativa["attempts"] = int(ativa.get("attempts", 0)) + 1
                ativa["status"] = "unavailable" if ativa["attempts"] >= 3 else "invalid"
            else:
                ativa["status"] = status_hipotese
            ativa["test"] = destino.relative_to(self.pasta).as_posix()
            ativa["result_detail"] = detalhe_hipotese
            resumo_hipotese: dict | None = None
            if vcd_hipotese.exists():
                resumo_hipotese = self._resumir_vcd(
                    vcd_hipotese, destino, cpu, detalhe_hipotese)
                resumo_path = vcd_hipotese.with_suffix(".summary.json")
                resumo_path.write_text(json.dumps(resumo_hipotese, indent=2,
                                                   ensure_ascii=False) + "\n",
                                       encoding="utf-8")
                ativa["vcd_summary"] = resumo_path.relative_to(self.pasta).as_posix()
            revisao: dict | None = None
            if status_hipotese in {"confirmed", "refuted"}:
                self.relatar("  reprodução pública: encaminhando teste e VCD ao revisor ...")
                revisao = self._revisar_hipotese_exploratoria(
                    ativa, destino, detalhe_hipotese, resumo_hipotese)
                ativa["review"] = revisao
                if not revisao["diagnostic_test_valid"]:
                    # A reprodução não mede a falha oficial; corrija este
                    # mesmo Cocotb, sem formular outra hipótese.
                    try:
                        self._corrigir_testbench(
                            cpu, destino, revisao.get("rationale", detalhe_hipotese),
                            tabela_falhas_cocotb(
                                revisao.get("rationale", detalhe_hipotese),
                                destino.read_text(encoding="utf-8", errors="replace")))
                    except ErroPlanoTeste as erro:
                        detalhe_hipotese = f"Testbench correction rejected: {erro}"
                    ativa["attempts"] = int(ativa.get("attempts", 0)) + 1
                    status_hipotese = "unavailable" if ativa["attempts"] >= 3 else "invalid"
                elif resultado_runtime == "assertion_failed":
                    # Um Cocotb que reproduz a falha arquitetural e passou a
                    # revisão semântica inicia uma correção VHDL candidata.
                    status_hipotese = "confirmed"
                else:
                    status_hipotese = "refuted"
                ativa["status"] = status_hipotese
                self.relatar(f"  revisão VCD: {status_hipotese.upper()} — "
                             f"{self._linha_curta(revisao.get('rationale'))}")
                self._registrar_reproducao_publica_do_diagnostico(
                    foco, estado, status_hipotese, destino)
            self._salvar_estado_exploracao_cpu(caminho, estado)
            self._log({"evento": "hipotese_causal_executada", "foco": foco,
                       "hipotese": ativa["hypothesis"], "arquivo": ativa["file"],
                       "status": ativa["status"], "teste": ativa["test"]})
            if status_hipotese == "confirmed":
                self._ultima_exploracao_falha = {
                    "foco": foco, "plano": nome_hipotese, "teste": destino,
                    "marcador": self._marcador_progresso_cocotb(ex_hipotese),
                }
                alvo_confirmado = str(ativa["file"])
                localizacao = ""
                if ativa.get("target_pending"):
                    alvo_confirmado, localizacao = self._escolher(
                        f"Confirmed causal hypothesis:\n{ativa['hypothesis']}\n\n"
                        f"Causal review:\n{json.dumps(ativa.get('review', {}), ensure_ascii=False)}\n\n"
                        f"Test execution:\n{detalhe_hipotese}", arq)
                    ativa["confirmed_file"] = alvo_confirmado
                    self._salvar_estado_exploracao_cpu(caminho, estado)
                return True, False, (f"Causal hypothesis confirmed by dedicated test: "
                                     f"{ativa['hypothesis']}\n{detalhe_hipotese}\n{localizacao}"), alvo_confirmado
            conclusao = (f" Review: {revisao.get('rationale', '')}" if revisao else "")
            return False, False, (
                f"Causal hypothesis `{ativa['hypothesis']}` was {ativa['status']}; "
                f"{conclusao}\n{detalhe_hipotese}"), None
    @staticmethod
    def _marcador_progresso_cocotb(ex: Execucao) -> tuple[int, float, int]:
        """Marco monotônico: passou, instante alcançado e assertion/linha alcançada."""
        rel = ex.relatorio or {}
        if rel.get("passed"):
            return 1, 10**30, 10**9
        texto = str(rel.get("diagnostico") or ex.saida)
        tempos = [float(valor) for valor in re.findall(
            r"\b(\d+(?:\.\d+)?)ns\b[^\n]*\bfailed\b", texto, re.IGNORECASE)]
        linhas = [int(valor) for valor in re.findall(r'File "[^"]+", line (\d+)', texto)]
        return 0, max(tempos, default=0.0), max(linhas, default=0)

    def _revalidar_progresso_exploratorio(self, cpu: dict, arq: dict,
                                           iteracao: int) -> tuple[bool, str]:
        """Reexecuta exatamente a observação que autorizou a correção."""
        base = self._ultima_exploracao_falha
        if not base:
            return False, "nenhuma exploração falha vinculada à correção"
        teste = Path(base["teste"])
        nome = str(base["plano"])
        ex = self.executor.rodar_componente(
            self.pasta, componente=cpu["name"], teste=teste,
            json_saida=self.sessao / "testes_resultados" /
            f"it{iteracao:02d}-progresso-{nome}.json",
            workdir=self.sessao / "sim" / f"progresso-it{iteracao:02d}-{nome}",
            build_root=self.sessao / "build" / f"progresso-it{iteracao:02d}-{nome}",
            fontes=self._fontes_do_bloco(cpu, arq) if self.gates_componentes else None)
        antes = tuple(base["marcador"])
        depois = self._marcador_progresso_cocotb(ex)
        resultado_valido = _falha_de_assertion(ex) or bool((ex.relatorio or {}).get("passed"))
        melhorou = resultado_valido and (depois[0] > antes[0] or depois[1] > antes[1] or
                                          depois[2] > antes[2])
        detalhe = (f"exploration `{nome}` marker {antes} -> {depois}; "
                   f"{'objective progress' if melhorou else 'no objective progress'}")
        self._log({"evento": "progresso_exploratorio_revalidado", "plano": nome,
                   "antes": antes, "depois": depois, "melhorou": melhorou,
                   "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
        return melhorou, detalhe

    def _registrar_progresso_parcial(self, foco: str, cpu: dict, detalhe: str,
                                     bloco_alterado: dict | None = None) -> bool:
        """Ativa nova rodada, com limite para impedir progresso infinitesimal infinito."""
        nome = re.sub(r"[^a-z0-9_]+", "_", foco.lower()).strip("_")
        historico_path = self.sessao / "exploracoes_cpu" / f"progresso_{nome}.json"
        try:
            historico = json.loads(historico_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, json.JSONDecodeError):
            historico = []
        alterado = bloco_alterado or cpu
        fonte_hash = hashlib.sha256(self._ler(alterado["file"]).encode("utf-8")).hexdigest()
        if len(historico) >= 8 or any(item.get("fonte_hash") == fonte_hash for item in historico):
            return False
        historico.append({"fonte_hash": fonte_hash, "detalhe": detalhe,
                          "t": datetime.now().isoformat(timespec="seconds")})
        historico_path.parent.mkdir(parents=True, exist_ok=True)
        historico_path.write_text(json.dumps(historico, indent=2, ensure_ascii=False) + "\n",
                                  encoding="utf-8")
        caminho, estado = self._estado_exploracao_cpu(foco, cpu)
        estado["ativado"] = True
        estado["progresso_anterior"] = detalhe
        self._salvar_estado_exploracao_cpu(caminho, estado)
        return True

    def _resumir_vcd(self, vcd: Path, teste: Path, bloco: dict, diagnostico: str) -> dict:
        """Seleciona sinais observáveis e extrai uma janela temporal genérica."""
        codigo = teste.read_text(encoding="utf-8", errors="replace")
        acessos = {p for p in self._caminhos_dut_no_ast(codigo) if p.count(".") == 1}
        portas = {f"dut.{nome}" for nome in re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*(?:in|out|inout)\b",
            self._interface_do_bloco(bloco), flags=re.IGNORECASE)}
        try:
            inventario = json.loads((self.sessao / "hierarquia" / f"{bloco['name']}.json").read_text(
                encoding="utf-8")).get("paths", [])
        except (OSError, ValueError, json.JSONDecodeError):
            inventario = []
        internos = {p for p in acessos if p in inventario and p not in portas}
        # Primeiro preserva sinais da assertion/teste; em seguida acrescenta
        # portas públicas. O limite torna o resumo utilizável pelo modelo.
        sinais = sorted(acessos | internos) + sorted(portas - acessos)
        sinais = list(dict.fromkeys(sinais))[:16]
        tempo = re.search(r"\b(\d+(?:\.\d+)?)ns\b.*?\bfailed\b", diagnostico,
                           re.IGNORECASE | re.DOTALL)
        falha_ns = float(tempo.group(1)) if tempo else None
        resumo = resumir_vcd(vcd, sinais, falha_ns=falha_ns)
        resumo["test"] = teste.relative_to(self.pasta).as_posix()
        resumo["assertion_context"] = diagnostico[-1200:]
        return resumo

    def _escrever_teste_interno(self, bloco: dict, arq: dict, caminhos: list[str]) -> Path | None:
        """Cria um único caso de integração interna a partir da hierarquia real."""
        interface = self._interface_do_bloco(bloco)
        portas = {f"dut.{nome}" for nome in re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*(?:in|out|inout)\b", interface,
            flags=re.IGNORECASE)}
        internos = [caminho for caminho in caminhos if caminho not in portas and
                    caminho.count(".") == 1]
        if not internos:
            self._log({"evento": "teste_interno_ignorado", "bloco": bloco["name"],
                       "motivo": "nenhum sinal interno exposto pelo simulador"})
            return None
        pasta = self.sessao / "testes_internos"
        numero = len(list(pasta.glob(f"test_{bloco['name']}_interno_*.py"))) + 1
        destino = pasta / f"test_{bloco['name']}_interno_{numero:02d}.py"
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Write one MINIMAL internal-integration Cocotb test for `{bloco['name']}`. "
                "This is a diagnostic integration layer, not a normative public regression. Use "
                "only public ports plus one or more paths from the simulator-confirmed inventory. "
                "Test exactly one causal connection across declared dependencies; do not test a "
                "program, ISA coverage, or multiple unrelated behaviors. Preserve the public "
                "interface contract and return one complete ```python block.\n\n"
                f"Component VHDL:\n```vhdl\n{self._ler(bloco['file'])}\n```\n\n"
                f"Direct dependency contracts:\n{self._especificacoes_dependencias(bloco, arq)}\n\n"
                f"Simulator-confirmed INTERNAL signals (use exact spellings only):\n"
                f"{json.dumps(internos)}\n\n"
                f"Public interface:\n```vhdl\n{self._interface_do_bloco(bloco)}\n```\n\n"
                f"{self._capacidade_assembly_rv32i(bloco)}\n"
                "The test must have exactly one @cocotb.test(), accept `dut`, and contain a "
                "focused assertion that directly reads at least one listed internal signal before "
                "any clock edge that would overwrite it. Copy the exact inventory spelling; do not "
                "invent a semantic name such as `next_pc`. "
                "Do not access an internal path absent from the inventory.")},
        ]
        self.relatar(f"  gerando teste interno de {bloco['name']} ...")

        def caminhos_lidos(codigo: str) -> set[str]:
            """Caminhos `dut.*` presentes no AST, nunca em comentário/docstring."""
            achados: set[str] = set()
            for no in ast.walk(ast.parse(codigo)):
                if not isinstance(no, ast.Attribute):
                    continue
                partes = [no.attr]
                valor = no.value
                while isinstance(valor, ast.Attribute):
                    partes.append(valor.attr)
                    valor = valor.value
                if isinstance(valor, ast.Name) and valor.id == "dut":
                    achados.add("dut." + ".".join(reversed(partes)))
            return achados

        motivo_rejeicao = ""
        for _ in range(3):
            r = self._chamar("teste_interno_componente",
                             destino.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            try:
                if not codigo:
                    motivo_rejeicao = "No Python module was extracted from the response."
                elif len(self._testes_cocotb(codigo)) != 1:
                    motivo_rejeicao = ("The module must contain exactly one @cocotb.test() "
                                        "function.")
                else:
                    ast.parse(codigo)
                    acessos = caminhos_lidos(codigo)
                    # `dut.signal.value` produz também o nó intermediário
                    # `dut.signal`; somente este é um path VPI a conferir.
                    sinais = {caminho for caminho in acessos if caminho.count(".") == 1}
                    nao_listados = sorted(sinais - portas - set(internos))
                    usa_interno = any(caminho in acessos for caminho in internos)
                    portas_instrucao = self._portas_de_instrucao_rv32i(bloco)
                    usa_assembly = (not portas_instrucao or
                                    self._novo_caso_usa_assembly_rv32i(
                                        codigo, set(self._testes_cocotb(codigo)), portas_instrucao,
                                        exigir_labels_controle=self._programa_rv32i_sequencial(bloco)))
                    if usa_interno and not nao_listados and usa_assembly:
                        destino.parent.mkdir(parents=True, exist_ok=True)
                        destino.write_text(codigo, encoding="utf-8")
                        self._log({"evento": "teste_interno_gerado", "bloco": bloco["name"],
                                   "arquivo": destino.relative_to(self.pasta).as_posix()})
                        return destino
                    if nao_listados:
                        motivo_rejeicao = ("Internal simulator path(s) absent from the inventory: "
                                            + ", ".join(f"`{p}`" for p in nao_listados) + ".")
                    elif not usa_interno:
                        motivo_rejeicao = "The test did not read any confirmed internal path."
                    else:
                        motivo_rejeicao = ("RV32I instruction stimulus must use valid "
                                            "`assemble_rv32i` source with real mnemonics and labels.")
            except SyntaxError as erro:
                motivo_rejeicao = f"Python syntax error: {erro.msg} (line {erro.lineno})."
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                             "The previous module was rejected by deterministic pre-Cocotb validation.\n"
                             f"Reason: {motivo_rejeicao}\n"
                             f"Use only these exact internal paths: {json.dumps(internos)}\n"
                             "Correct the same diagnostic and return one complete module with exactly "
                             "one Cocotb test. RV32I assembly must use `assemble_rv32i` with labels "
                             "(never numeric JAL/branch targets) and real mnemonics (never `j` or `nop`)."}]
        raise ErroGeracao(f"o modelo nao produziu teste interno valido para {bloco['file']}")

    def _ampliar_teste_interno(self, bloco: dict, teste: Path, plano: str,
                                caminhos: list[str]) -> Path:
        """Acrescenta uma única conexão causal à suíte interna já aprovada."""
        atual = teste.read_text(encoding="utf-8", errors="replace")
        existentes = self._testes_cocotb(atual)
        internos = {p for p in caminhos if p.count(".") == 1}
        portas = {f"dut.{nome}" for nome in re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*(?:in|out|inout)\b",
            self._interface_do_bloco(bloco), flags=re.IGNORECASE)}
        internos -= portas
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Expand the passing INTERNAL Cocotb integration suite for `{bloco['name']}`. "
                "Add exactly one @cocotb.test() for the supplied plan. Preserve every existing "
                "test function unchanged. This is diagnostic-only and must read one or more exact "
                "simulator-confirmed internal signals, while using public ports only to drive inputs. "
                "It must exercise exactly one new causal dependency connection, not a public ISA "
                "program or a broad regression. For RV32I instruction inputs, use `assemble_rv32i` "
                "with real instructions and labels; never calculate encodings or use numeric JAL/branch "
                "targets. Return one complete Python module.\n\n"
                f"One new-case plan:\n{plano}\n\n"
                f"Confirmed internal paths:\n{json.dumps(sorted(internos))}\n\n"
                f"Current passing internal suite:\n```python\n{atual}\n```")},
        ]
        self.relatar(f"  ampliando integracao interna de {bloco['name']} ...")
        ultimo_candidato = "(nenhum código Python extraído)"
        for _ in (1, 2):
            r = self._chamar("ampliacao_teste_interno",
                             teste.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            ultimo_candidato = (codigo or r.texto)[-3000:]
            try:
                if codigo:
                    ast.parse(codigo)
                    novos = self._testes_cocotb(codigo)
                    adicionados = set(novos) - set(existentes)
                    preservados = all(novos.get(nome) == corpo for nome, corpo in existentes.items())
                    if len(adicionados) == 1 and len(novos) == len(existentes) + 1 and preservados:
                        funcao = next(no for no in ast.parse(codigo).body
                                      if isinstance(no, (ast.FunctionDef, ast.AsyncFunctionDef)) and
                                      no.name in adicionados)
                        usa_interno = bool(internos & self._caminhos_dut_no_ast(ast.unparse(funcao)))
                        usa_assembly = (not self._portas_de_instrucao_rv32i(bloco) or
                                        self._novo_caso_usa_assembly_rv32i(
                                            codigo, adicionados, self._portas_de_instrucao_rv32i(bloco),
                                            exigir_labels_controle=self._programa_rv32i_sequencial(bloco)))
                        if usa_interno and usa_assembly:
                            teste.write_text(codigo, encoding="utf-8")
                            self._log({"evento": "teste_interno_caso_adicionado",
                                       "bloco": bloco["name"],
                                       "arquivo": teste.relative_to(self.pasta).as_posix(),
                                       "caso": next(iter(adicionados))})
                            return teste
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Send valid Python preserving every prior test and adding one internal test "
                            "that reads an exact inventory path and uses valid label-based RV32I assembly."}]
        raise ErroPlanoTeste(
            f"candidato interno recusado: nao preservou a suite, probe VPI ou assembly RV32I em "
            f"{bloco['file']}. Candidato rejeitado:\n```python\n{ultimo_candidato}\n```")

    def _largura_da_porta(self, bloco: dict, porta: str) -> int | None:
        """Largura contratada na decomposicao, quando a porta e um vetor simples."""
        for declaracao in bloco["ports"]:
            m = re.search(rf"\b{re.escape(porta)}\s*:\s*(?:in|out)\s+"
                          r"std_logic_vector\s*\(\s*(\d+)\s+downto\s*(\d+)\s*\)",
                          declaracao, re.IGNORECASE)
            if m:
                return int(m.group(1)) - int(m.group(2)) + 1
        return None

    def _triagem_componente(self, ex: Execucao, bloco: dict, teste: Path) -> tuple[str, str]:
        """Decide se a evidencia acusa DUT, testbench ou precisa de revisao.

        A LLM recebe ambos os arquivos, mas uma excecao de largura confirmada
        pela porta contratual vence sua opiniao: e evidencia objetiva de que o
        Python tentou dirigir um valor invalido antes de observar o DUT.
        """
        rel = ex.relatorio or {}
        diagnostico = str(rel.get("diagnostico") or rel.get("detail") or ex.saida[-4000:])
        fonte_teste = teste.read_text(encoding="utf-8", errors="replace")
        fonte_vhdl = self._ler(bloco["file"])
        tabela_falhas = tabela_falhas_cocotb(diagnostico, fonte_teste)
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                "Classify this component-test failure. Answer ONLY JSON with `causa` "
                "(`vhdl`, `testbench`, `spec`, or `ambigua`) and concise `evidencias`. Use "
                "`spec` only for an explicit contradiction or missing/ambiguous semantic rule "
                "in the normative component contract. A Python "
                "exception before an assertion normally means testbench; an assertion after "
                "the DUT executes normally means VHDL. Do not propose a fix.\n\n"
                f"Component contract ports: {'; '.join(bloco['ports'])}\n\n"
                f"Normative semantic contract:\n{self._ler_especificacao(bloco)}\n\n"
                 f"Simulator diagnostic:\n```text\n{diagnostico}\n```\n\n"
                 f"{tabela_falhas}\n\n"
                 f"Testbench ({teste.name}):\n```python\n{fonte_teste}\n```\n\n"
                f"DUT ({bloco['file']}):\n```vhdl\n{fonte_vhdl}\n```")},
        ]
        causa, evidencias = "ambigua", ["a resposta de triagem nao era JSON valido"]
        for tentativa in (1, 2, 3):
            r = self._chamar("triagem_componente", teste.relative_to(self.pasta).as_posix(),
                             mensagens, schema=_SCHEMA_TRIAGEM_COMPONENTE)
            try:
                resposta = extrair_json(r.texto)
                causa = str(resposta.get("causa", "ambigua"))
                brutas = resposta.get("evidencias", [])
            # Alguns provedores aceitam o schema, mas ainda devolvem uma unica
            # string em vez do array pedido. Iterar uma string a transforma em
            # uma lista de caracteres, polui o log e pode tornar a triagem
            # inutilizavel. Aceitamos o desvio como uma evidencia unica.
                if isinstance(brutas, str):
                    evidencias = [brutas.strip()] if brutas.strip() else []
                elif isinstance(brutas, list):
                    evidencias = [str(x).strip() for x in brutas if str(x).strip()]
                else:
                    evidencias = []
                if causa in ("vhdl", "testbench", "spec", "ambigua"):
                    break
            except (ErroLLM, AttributeError):
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Your previous answer was not valid JSON. Reply ONLY with one JSON object "
                            "matching this schema: {\"causa\": \"vhdl|testbench|spec|ambigua\", "
                            "\"evidencias\": [\"concise evidence\"]}. Do not include analysis or Markdown."}]
        if causa not in ("vhdl", "testbench", "spec", "ambigua"):
            causa = "ambigua"

        # Cocotb 2 devolve LogicArray, e ``int(valor, 2)`` e sempre um erro
        # do Python antes de observar o comportamento do DUT. Warnings de
        # metavalue na inicializacao nao tornam essa excecao ambigua.
        conversao_cocotb = re.search(
            r"int\(\) can't convert non-string with explicit base", diagnostico)
        if conversao_cocotb:
            causa = "testbench"
            evidencias.append("`int(sinal.value, 2)` e invalido no cocotb 2; use "
                               "`int(sinal.value)` para um sinal resolvido")

        # Cocotb sempre chama a coroutine decorada com o handle do DUT. Uma
        # assinatura sem ``dut`` falha antes de qualquer delta de simulação e
        # não pode ser atribuída ao VHDL ou à spec semântica.
        assinatura_cocotb = re.search(
            r"takes 0 positional arguments? but 1 was given", diagnostico)
        if assinatura_cocotb:
            causa = "testbench"
            evidencias.append("a coroutine @cocotb.test() nao aceita o argumento `dut`; "
                               "declare `async def nome_do_teste(dut):`")

        largura = re.search(r"Int value \([^)]*\) out of range for assignment of "
                            r"(\d+)-bit signal \('([^']+)'\)", diagnostico)
        if largura:
            bits, porta = int(largura.group(1)), largura.group(2)
            esperada = self._largura_da_porta(bloco, porta)
            if esperada == bits:
                causa = "testbench"
                evidencias.append(f"{porta} e contratualmente {bits}-bit e o Python tentou "
                                   "atribuir um valor fora dessa largura")
        texto = "\n".join(f"- {e}" for e in evidencias[:6]) or "- sem evidencia util"
        self._log({"evento": "triagem_componente", "bloco": bloco["name"],
                   "testbench": teste.relative_to(self.pasta).as_posix(), "causa": causa,
                   "evidencias": evidencias})
        return causa, texto

    def _corrigir_testbench(self, bloco: dict, teste: Path, evidencia: str,
                            tabela_falhas: str = "") -> Path:
        """Corrige somente um testbench que falhou antes de testar o DUT."""
        atual = teste.read_text(encoding="utf-8", errors="replace")
        interno = teste.parent in {
            self.sessao / "testes_internos",
            self.sessao / "diagnosticos_internos",
            self.sessao / "exploracoes_cpu",
        }
        try:
            inventario = json.loads((self.sessao / "hierarquia" /
                                     f"{bloco['name']}.json").read_text(encoding="utf-8"))
            caminhos_internos = {p for p in inventario.get("paths", []) if p.count(".") == 1}
        except (OSError, json.JSONDecodeError, AttributeError):
            caminhos_internos = set()
        portas_publicas = {f"dut.{nome}" for nome in re.findall(
            r"\b([A-Za-z][A-Za-z0-9_]*)\s*:\s*(?:in|out|inout)\b",
            self._interface_do_bloco(bloco), flags=re.IGNORECASE)}
        caminhos_internos -= portas_publicas
        camada = (" This is an internal diagnostic integration test: preserve a direct read of "
                  "at least one simulator-confirmed internal signal." if interno else "")
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Fix ONLY this complete Cocotb Python testbench for `{bloco['name']}`. "
                "Do NOT change VHDL, remove assertions, or weaken expected behavior. Preserve "
                "the test intent. Ensure every value assigned to a DUT port fits its declared "
                 f"width (use masking when testing RV32 wraparound).{camada}\n\n"
                 f"Failure evidence:\n{evidencia}\n\nCurrent testbench:\n```python\n{atual}\n```\n\n"
                 f"{tabela_falhas}\n\n"
                 "Every row in the failure table is from the same execution. Correct ALL of "
                 "them, while preserving the asserted semantic intent.\n\n"
                 "Answer only with the complete corrected testbench in one ```python block.")},
        ]
        for _ in (1, 2):
            r = self._chamar("correcao_testbench", teste.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            nao_inventados: list[str] = []
            try:
                if codigo and self._modulo_cocotb_valido(codigo):
                    acessos = self._caminhos_dut_no_ast(codigo)
                    conserva_interno = not interno or bool(caminhos_internos & acessos)
                    sinais = {p for p in acessos if p.count(".") == 1}
                    nao_inventados = sorted(sinais - portas_publicas - caminhos_internos)
                    portas_instrucao = self._portas_de_instrucao_rv32i(bloco)
                    exige_assembly = bool(portas_instrucao) and (interno or
                                                                  self._montador_de_estimulos() in atual)
                    conserva_assembly = (not exige_assembly or
                                          self._montador_de_estimulos() in codigo)
                    if conserva_interno and conserva_assembly and not nao_inventados:
                        teste.write_text(codigo, encoding="utf-8")
                        self._log({"evento": "testbench_corrigido", "bloco": bloco["name"],
                                   "arquivo": teste.relative_to(self.pasta).as_posix()})
                        return teste
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                            "Send a complete syntactically valid Cocotb module in one ```python block. "
                            f"Preserve all required internal probes and the {self._montador_de_estimulos()} call. "
                            f"Every DUT path must be either a public port or one of these exact "
                            f"simulator-confirmed internal paths: {json.dumps(sorted(caminhos_internos))}. "
                            f"Do not use unconfirmed paths such as: {json.dumps(nao_inventados)}."}]
        raise ErroPlanoTeste(
            f"correcao Cocotb recusada: nao preservou os requisitos da camada em {bloco['file']}")

    def _escrever_diagnostico_componente(self, bloco: dict, evidencia: str) -> Path:
        """Cria um segundo teste mínimo, independente do que falhou.

        Ele é usado apenas quando a primeira triagem não consegue separar DUT
        de testbench. Não recebe o código do teste original, para não repetir
        suas suposições ou seus erros de API.
        """
        pasta = self.sessao / "diagnosticos"
        numero = len(list(pasta.glob(f"test_{bloco['name']}_diagnostico_*.py"))) + 1
        destino = pasta / f"test_{bloco['name']}_diagnostico_{numero:02d}.py"
        interface = self._interface_do_bloco(bloco)
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Write an independent, MINIMAL Cocotb diagnostic testbench `{destino.name}` "
                f"for entity `{bloco['name']}`. It must use only these declared ports: "
                f"{'; '.join(bloco['ports'])}. Do NOT copy, inspect, or assume anything about "
                "the earlier testbench. Initialize every input and test the smallest behavior "
                "needed to distinguish an implementation failure from a testbench failure. "
                "Use exactly one @cocotb.test(), one focused assertion, and one ```python "
                "block only. Do not turn it into a broad regression suite.\n\n"
                f"Component responsibility: {bloco['responsibility']}\n"
                f"Normative component semantic contract:\n{self._ler_especificacao(bloco)}\n\n"
                f"Earlier failure evidence (may be wrong; use it only to choose the behavior):\n"
                f"{evidencia}\n\nPublic DUT interface:\n```vhdl\n{interface}\n```")},
        ]
        for _ in (1, 2):
            r = self._chamar("diagnostico_componente",
                             destino.relative_to(self.pasta).as_posix(), mensagens)
            codigo = extrair_python(r.texto)
            try:
                if codigo:
                    ast.parse(codigo)
                    destino.parent.mkdir(parents=True, exist_ok=True)
                    destino.write_text(codigo, encoding="utf-8")
                    self._log({"evento": "diagnostico_gerado", "bloco": bloco["name"],
                               "arquivo": destino.relative_to(self.pasta).as_posix()})
                    return destino
            except SyntaxError:
                pass
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Send a complete syntactically valid minimal Cocotb diagnostic "
                            "module in one ```python block."}]
        raise ErroGeracao(f"nao foi possivel criar diagnostico para {bloco['file']}")

    def _resolver_ambiguidade_componente(self, bloco: dict, teste: Path, arq: dict,
                                          evidencia: str) -> tuple[str, str, Execucao | None, Path | None]:
        """Executa e, se necessário, corrige um oráculo independente.

        A correção é feita pela LLM a partir do log real, como em qualquer
        testbench. Não há tratamento especial para uma API, entidade ou porta.
        """
        self.relatar(f"  triagem ambigua: criando diagnostico independente de {bloco['name']} ...")
        try:
            diagnostico = self._escrever_diagnostico_componente(bloco, evidencia)
        except ErroGeracao as erro:
            # A incapacidade de a LLM produzir um pequeno arquivo Python não é
            # evidência sobre o DUT e não deve encerrar a geração. O chamador
            # escala esta ambiguidade para o revisor de convergência com o erro
            # de protocolo registrado, tal como faz para um diagnóstico que
            # executou mas não foi conclusivo.
            detalhe = f"- nao foi possivel gerar diagnostico independente: {erro}"
            self._log({"evento": "diagnostico_indisponivel", "bloco": bloco["name"],
                       "evidencia": detalhe})
            return "ambigua", detalhe, None, None
        for tentativa in range(2):
            rotulo = diagnostico.stem.replace("test_", "") + ("" if tentativa == 0 else f"-it{tentativa:02d}")
            ex = self.executor.rodar_componente(
                self.pasta, componente=bloco["name"], teste=diagnostico,
                json_saida=self.sessao / "testes_resultados" / f"{rotulo}.json",
                workdir=self.sessao / "sim" / f"componente-{rotulo}",
                build_root=self.sessao / "build" / f"componente-{bloco['name']}",
                fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None)
            passou = bool((ex.relatorio or {}).get("passed"))
            self._log({"evento": "diagnostico_componente", "bloco": bloco["name"],
                       "testbench": diagnostico.relative_to(self.pasta).as_posix(),
                       "comando": ex.comando, "codigo": ex.codigo, "passou": passou,
                       "segundos": ex.segundos, "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
            self.relatar(f"  diagnostico {bloco['name']:<11} {'ok' if passou else 'FALHOU'} ({ex.segundos} s)")
            if passou:
                return "testbench", ("- o diagnostico independente passou; o testbench original "
                                       "e a fonte da falha"), None, diagnostico
            causa, evidencias = self._triagem_componente(ex, bloco, diagnostico)
            if causa in ("vhdl", "spec"):
                return causa, evidencias, ex, None
            if causa == "testbench" and tentativa == 0:
                tabela = tabela_falhas_cocotb(
                    str((ex.relatorio or {}).get("diagnostico") or ex.saida),
                    diagnostico.read_text(encoding="utf-8", errors="replace"))
                self.relatar(f"  corrigindo diagnostico independente de {bloco['name']} ...")
                diagnostico = self._corrigir_testbench(bloco, diagnostico, evidencias, tabela)
                continue
            return "ambigua", ("- o diagnostico independente tambem nao foi utilizavel; nenhum "
                                f"arquivo foi alterado:\n{evidencias}"), None, None
        raise AssertionError("laco de diagnostico deveria sempre retornar")

    def _promover_diagnostico_publico(self, bloco: dict, diagnostico: Path,
                                      teste: Path) -> bool:
        """Promove um oráculo público mínimo que passou para substituir smoke inválido."""
        if teste != self._caminho_teste(bloco):
            return False
        codigo = diagnostico.read_text(encoding="utf-8", errors="replace")
        try:
            if not self._smoke_cocotb_valido(codigo):
                return False
        except SyntaxError:
            return False
        teste.write_text(codigo, encoding="utf-8")
        self._log({"evento": "diagnostico_promovido_a_smoke", "bloco": bloco["name"],
                   "origem": diagnostico.relative_to(self.pasta).as_posix(),
                   "destino": teste.relative_to(self.pasta).as_posix()})
        self.relatar(f"  diagnostico publico confirmou erro Cocotb; promovendo-o a smoke de "
                      f"{bloco['name']} ...")
        return True

    def _compilar_antes_dos_testes(self, arq: dict, usados: int) -> int:
        """Gate de compilacao global antes de criar qualquer testbench."""
        arquivos = [b["file"] for b in arq["blocks"]]
        atual = self._validar("pre-testes-fumaca", "rv32i", [self.caso_de_fumaca()])
        while not placar_de(atual).compilou:
            if usados >= self.iteracoes:
                raise ErroGeracao("orcamento esgotado antes dos testbenches: a CPU nao compila")
            usados += 1
            alvo, evidencia = self._evidencia(atual, arquivos)
            if alvo is None:
                alvo, localizacao = self._escolher(evidencia, arq)
                evidencia += "\n\n" + localizacao
            self.relatar(f"  iteracao {usados}/{self.iteracoes}: corrigindo {alvo} para compilar ...")
            novo = self._reescrever(alvo, evidencia, arq, None)
            if novo is None:
                continue
            self._escrever(alvo, novo)
            atual = self._validar(f"pre-testes-it{usados:02d}", "rv32i", [self.caso_de_fumaca()])
        return usados

    def _fontes_do_bloco(self, bloco: dict, arq: dict) -> list[Path]:
        """Clausura transitiva das dependências declaradas do bloco.

        Fontes de CPUs de referência não pertencem ao componente gerado: além
        de mascararem dependências ausentes, podem introduzir ROM/RAM ou nomes
        reservados sem relação com a interface virtual da entrega.
        """
        por_nome = {b["name"]: b for b in arq["blocks"]}
        nomes: list[str] = []

        def visitar(nome: str) -> None:
            if nome in nomes:
                return
            for dep in por_nome[nome].get("depends_on", []):
                visitar(dep)
            nomes.append(nome)

        visitar(bloco["name"])
        return [self._destino(por_nome[n]["file"]) for n in nomes]

    def _congelar_bloco(self, bloco: dict) -> None:
        """Registra a versao aprovada; alteracoes posteriores exigem novo teste."""
        fonte = self._destino(bloco["file"])
        testes = sorted(p.relative_to(self.sessao).as_posix()
                        for p in (self.sessao / "testes").glob(f"test_{bloco['name']}*.py"))
        testes += sorted(p.relative_to(self.sessao).as_posix()
                         for p in (self.sessao / "regressoes").glob(f"test_{bloco['name']}*.py"))
        registro = {"bloco": bloco["name"], "arquivo": bloco["file"],
                    "hash_vhdl": hash_de([fonte]), "testes": testes}
        destino = self.sessao / "componentes_aprovados" / f"{bloco['name']}.json"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(json.dumps(registro, indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        self._log({"evento": "componente_aprovado", **registro,
                   "registro": destino.relative_to(self.pasta).as_posix()})

    def _invalidar_dependentes_da_especificacao(self, bloco: dict, arq: dict) -> None:
        """Regera VHDL dos consumidores da spec revisada, em ordem topológica."""
        afetados = {bloco["name"]}
        mudou = True
        while mudou:
            mudou = False
            for candidato in arq["blocks"]:
                if candidato["name"] not in afetados and \
                        any(dep in afetados for dep in candidato.get("depends_on", [])):
                    afetados.add(candidato["name"])
                    mudou = True
        for candidato in arq["blocks"]:
            if candidato["name"] == bloco["name"] or candidato["name"] not in afetados:
                continue
            # No modo com portões, dependentes ainda não foram escritos. No
            # modo normal, eles já existem e precisam consumir o novo contrato.
            if self._destino(candidato["file"]).exists():
                self._escrever_bloco(candidato, arq)
        nomes = sorted(afetados - {bloco["name"]})
        self._log({"evento": "dependentes_spec_invalidados", "bloco": bloco["name"],
                   "dependentes": nomes})

    def _regerar_dependencias_semanticas_revisadas(self, arq: dict, usados: int) -> int:
        """Reconstrói e revalida dependências cujo contrato mudou na revisão do topo."""
        if not self._dependencias_semanticas_revisadas:
            return usados
        nomes = self._dependencias_semanticas_revisadas
        blocos = [bloco for bloco in arq["blocks"] if bloco["name"] in nomes]
        self._dependencias_semanticas_revisadas = set()
        self.relatar("  revalidando dependencia(s) após revisão semântica de integração: "
                      + ", ".join(bloco["name"] for bloco in blocos))
        for dependencia in blocos:
            self._escrever_bloco(dependencia, arq)
            usados = self._testar_componentes(arq, usados, [dependencia])
            self._congelar_bloco(dependencia)
        return usados

    def _revisar_convergencia_componente(self, bloco: dict, teste: Path,
                                         historico: list[str]) -> tuple[str, str]:
        """Revisor de segundo nível para correções que não estão convergindo."""
        contexto = "\n\n".join(historico[-2:])
        mensagens = [
            {"role": "system", "content": self.contrato_testes},
            {"role": "user", "content": (
                f"Act as an independent convergence reviewer for component `{bloco['name']}`. "
                "Several corrective attempts failed consecutively. Review the semantic contract, "
                "the current VHDL, the current Cocotb testbench, and the failure history together. "
                "Do not impose an internal decomposition or rewrite any file. Decide what must be "
                "changed first. Reply in Markdown with exactly these sections:\n"
                "## Verdict\nOne of: `vhdl`, `testbench`, `spec`, or `mixed`.\n"
                "## Evidence\nConcise bullets.\n"
                "## Next action\nConcise ordered actions.\n\n"
                f"Semantic contract:\n{self._ler_especificacao(bloco)}\n\n"
                f"Current VHDL:\n```vhdl\n{self._ler(bloco['file'])}\n```\n\n"
                f"Current Cocotb testbench:\n```python\n"
                f"{teste.read_text(encoding='utf-8', errors='replace')}\n```\n\n"
                f"Recent failure history:\n{contexto}")},
        ]
        self.relatar(f"  revisando convergencia de {bloco['name']} ...")
        for _ in (1, 2):
            r = self._chamar("revisao_convergencia_componente",
                             teste.relative_to(self.pasta).as_posix(), mensagens,
                             temperatura=0.0)
            m = re.search(r"(?im)^##\s*Verdict\s*\n\s*`?(vhdl|testbench|spec|mixed)`?\s*$",
                          r.texto)
            if m:
                veredito = m.group(1).lower()
                self._log({"evento": "revisao_convergencia_componente", "bloco": bloco["name"],
                           "veredito": veredito, "resposta": r.texto})
                return veredito, r.texto
            mensagens += [{"role": "assistant", "content": r.texto},
                           {"role": "user", "content":
                            "Return Markdown with `## Verdict`, `## Evidence`, and `## Next action`; "
                            "the verdict must be vhdl, testbench, spec, or mixed."}]
        raise ErroGeracao(f"o revisor de convergencia nao classificou {bloco['file']}")

    def _testar_componentes(self, arq: dict, usados: int,
                            blocos: list[dict] | None = None,
                            reutilizar_testes: bool = False) -> int:
        """Gera e roda um testbench por VHDL; falha executada volta ao VHDL."""
        arquivos = [b["file"] for b in arq["blocks"]]
        self._mostrar_fluxo(3)
        self.relatar(f"{self._fase(3)} testbenches dos componentes ...")
        for bloco in blocos or arq["blocks"]:
            teste = self._caminho_teste(bloco)
            reutilizou_teste = reutilizar_testes and teste.exists()
            if not reutilizou_teste:
                teste = self._escrever_testbench(bloco)
            else:
                self._log({"evento": "testbench_retomado", "bloco": bloco["name"],
                           "arquivo": teste.relative_to(self.pasta).as_posix()})
                self.relatar(f"  retomando testbench existente de {bloco['name']} ...")
            # Casos incrementais promovidos são módulos imutáveis e autônomos.
            # Na retomada, execute-os novamente após o smoke sem solicitar que
            # a LLM reescreva qualquer arquivo já aprovado.
            testes = [teste, *self._casos_publicos_isolados(bloco)]
            # Cada expansão é um candidato. A cópia aprovada é restaurada se
            # sua simulação/correção falhar, antes de pedir novo plano.
            snapshot_inicial = self._caminho_snapshot_teste(teste)
            texto_aprovado = (snapshot_inicial.read_text(encoding="utf-8", errors="replace")
                              if snapshot_inicial.exists() else
                              teste.read_text(encoding="utf-8", errors="replace"))
            suites_aprovadas: dict[Path, str] = {
                teste: texto_aprovado}
            # Na retomada, só deixamos de acrescentar casos quando a sessão
            # registrou explicitamente que a expansão incremental terminou.
            expansao_concluida = reutilizou_teste and self._expansao_testbench_concluida(bloco)
            inventario_feito = not bool(bloco.get("depends_on")) or \
                (self.sessao / "hierarquia" / f"{bloco['name']}.json").exists()
            internos_concluidos = not (self.testes_internos and bloco.get("depends_on"))
            interno_agendado = False
            rejeicao_plano_publico = ""
            replanejamentos_publicos = 0
            rejeicao_plano_interno = ""
            replanejamentos_internos = 0
            evidencia_para_regressao: str | None = None
            regressao_criada = False
            falhas_corretivas = 0
            historico_falhas: list[str] = []
            # Uma correção de Cocotb é um candidato, não uma nova verdade.
            # Sem este limite o modelo pode editar indefinidamente a mesma
            # expansão reprovada, perdendo a última suíte aprovada.
            correcoes_cocotb_do_candidato = 0
            # Um parecer de convergência que atribui a falha ao Cocotb é uma
            # restrição causal persistente do candidato, não uma sugestão que
            # a próxima triagem pode ignorar e usar para autorizar VHDL.
            candidatos_bloqueados_vhdl: set[Path] = set()
            parallel_testes_efetivo = self.parallel_testes
            lotes_paralelos_sem_aprovacao = 0
            # Candidatos que chegaram ao Cocotb e falharam são evidência
            # pendente, não lixo descartável. Eles passam pelo mesmo fluxo de
            # triagem/correção antes de qualquer novo planejamento.
            pendentes_publicos = self._pendentes_publicos_da_ultima_sessao(bloco) \
                if reutilizou_teste else []
            if pendentes_publicos:
                testes.insert(1, pendentes_publicos[0])
                self.relatar(f"  retomando {len(pendentes_publicos)} candidato(s) publico(s) "
                              f"pendente(s) antes de novo planejamento para {bloco['name']} ...")
            lote_incremental = len(list((self.sessao / "testes_candidatos" /
                                         bloco["name"]).glob("lote-*"))) \
                if (self.sessao / "testes_candidatos" / bloco["name"]).exists() else 0
            indice = 0
            while True:
                if indice == len(testes):
                    if self.regressoes_componentes and evidencia_para_regressao and not regressao_criada:
                        testes.append(self._escrever_regressao(
                            bloco, evidencia_para_regressao, len(testes)))
                        regressao_criada = True
                        continue
                    break
                teste_atual = testes[indice]
                sufixo = teste_atual.stem.replace("test_", "")
                rotulo = sufixo if usados == 0 else f"{sufixo}-it{usados:02d}"
                nomes_testes = self._testes_cocotb(
                    teste_atual.read_text(encoding="utf-8", errors="replace"))
                quantidade_testes = len(nomes_testes)
                nome_modulo = teste_atual.name
                funcoes = ", ".join(nomes_testes) or "(nenhum @cocotb.test detectado)"
                # Durante a expansão, o primeiro módulo é reexecutado como
                # smoke entre candidatos; ele não é o "caso 1" de uma suíte
                # que ainda está crescendo. Depois do encerramento, a lista
                # contém exatamente os módulos que serão percorridos.
                progresso_global = ("smoke" if teste_atual == teste and not expansao_concluida
                                    else f"caso {indice + 1}/{len(testes)}")
                plural = "teste" if quantidade_testes == 1 else "testes"
                self.relatar(f"  suite {bloco['name']:<16} {progresso_global} "
                              f"{nome_modulo} [{quantidade_testes} {plural} no arquivo]: "
                              f"executando {funcoes} ...")
                ex = self.executor.rodar_componente(
                    self.pasta, componente=bloco["name"], teste=teste_atual,
                    json_saida=self.sessao / "testes_resultados" / f"{rotulo}.json",
                    workdir=self.sessao / "sim" / f"componente-{rotulo}",
                    build_root=self.sessao / "build" / f"componente-{bloco['name']}",
                    fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None)
                rel = ex.relatorio or {}
                passou = bool(rel.get("passed"))
                self._log({"evento": "teste_componente", "bloco": bloco["name"],
                           "testbench": teste_atual.relative_to(self.pasta).as_posix(),
                           "comando": ex.comando, "codigo": ex.codigo, "passou": passou,
                           "segundos": ex.segundos, "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
                self.relatar(f"  teste {bloco['name']:<16} {progresso_global} {nome_modulo} "
                              f"[{quantidade_testes} {plural}] "
                              f"{'ok' if passou else 'FALHOU'} ({ex.segundos} s)")
                if passou:
                    falhas_corretivas = 0
                    historico_falhas.clear()
                    correcoes_cocotb_do_candidato = 0
                    suites_aprovadas[teste_atual] = teste_atual.read_text(
                        encoding="utf-8", errors="replace")
                    snapshot = self._caminho_snapshot_teste(teste_atual)
                    snapshot.parent.mkdir(parents=True, exist_ok=True)
                    snapshot.write_text(suites_aprovadas[teste_atual], encoding="utf-8")
                    if teste_atual in pendentes_publicos:
                        lote_pendente = teste_atual.parent.name
                        oficial = (self.sessao / "testes_casos" / bloco["name"] / "publicos" /
                                    f"pendente-{lote_pendente}-{teste_atual.name}")
                        oficial.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(teste_atual, oficial)
                        posicao_pendente = pendentes_publicos.index(teste_atual)
                        pendentes_publicos.pop(posicao_pendente)
                        testes[indice] = oficial
                        self._log({"evento": "candidato_pendente_aprovado", "bloco": bloco["name"],
                                   "origem": teste_atual.relative_to(self.pasta).as_posix(),
                                   "arquivo": oficial.relative_to(self.pasta).as_posix()})
                        self.relatar(f"  candidato pendente de {bloco['name']} foi aprovado; "
                                      "promovendo caso isolado ...")
                        if pendentes_publicos:
                            testes.insert(indice + 1, pendentes_publicos[0])
                            indice += 1
                        else:
                            indice = 0
                        continue
                    if (teste_atual.parent == self.sessao / "testes_internos" and
                            not internos_concluidos):
                        casos_internos = quantidade_testes + len(self._casos_internos_isolados(bloco))
                        if casos_internos > self.max_casos_internos:
                            raise ErroGeracao(
                                f"limite de {self.max_casos_internos} casos internos excedido em "
                                f"{bloco['file']} sem decisao COMPLETE do orquestrador")
                        try:
                            decisao_interna = self._decidir_expansao_testbench(
                                bloco, teste_atual, interno=True,
                                rejeicao_anterior=rejeicao_plano_interno,
                                casos_aprovados=casos_internos,
                                contexto_suite=self._contexto_interno_isolado(bloco, teste_atual))
                        except ErroGeracao as erro:
                            replanejamentos_internos += 1
                            rejeicao_plano_interno = str(erro)
                            self._log({"evento": "orquestracao_interna_rejeitada",
                                       "bloco": bloco["name"], "tentativa": replanejamentos_internos,
                                       "motivo": rejeicao_plano_interno})
                            self.relatar("  orquestrador interno invalido; replanejando "
                                          f"({replanejamentos_internos}/3) ...")
                            if replanejamentos_internos >= 3:
                                raise ErroGeracao(
                                    f"orquestracao interna esgotada em {bloco['file']}: "
                                    f"{rejeicao_plano_interno}")
                            continue
                        if decisao_interna is not None:
                            if casos_internos >= self.max_casos_internos:
                                raise ErroGeracao(
                                    f"limite de {self.max_casos_internos} casos internos atingido em "
                                    f"{bloco['file']} sem decisao COMPLETE do orquestrador")
                            plano_interno, _ = decisao_interna
                            self.relatar(f"  integracao interna {bloco['name']:<4} ADD: preparando "
                                          f"incremento {casos_internos + 1}/{self.max_casos_internos} ...")
                            self.relatar(f"    racional: {self._resumo_plano_incremental(plano_interno)}")
                            self._registrar_plano_incremental(
                                bloco, camada="interna", numero=casos_internos + 1, plano=plano_interno)
                            self._log({"evento": "plano_teste_incremental", "bloco": bloco["name"],
                                       "camada": "interna", "resumo": self._resumo_plano_incremental(plano_interno)})
                            try:
                                caminhos = json.loads((self.sessao / "hierarquia" /
                                                      f"{bloco['name']}.json").read_text(
                                                          encoding="utf-8")).get("paths", [])
                            except (OSError, json.JSONDecodeError, AttributeError):
                                caminhos = []
                            try:
                                raiz_candidata = self.sessao / "testes_candidatos" / bloco["name"] / "internos"
                                candidato = raiz_candidata / f"caso-{casos_internos + 1:02d}.py"
                                self._escrever_caso_interno_isolado(
                                    bloco, candidato, plano_interno, caminhos, teste_atual)
                                rotulo_interno = f"{bloco['name']}-interno-{casos_internos + 1:02d}"
                                ex_interno = self.executor.rodar_componente(
                                    self.pasta, componente=bloco["name"], teste=candidato,
                                    json_saida=self.sessao / "testes_resultados" / f"{rotulo_interno}.json",
                                    workdir=self.sessao / "sim" / f"componente-{rotulo_interno}",
                                    build_root=self.sessao / "build" / f"componente-{rotulo_interno}",
                                    fontes=self._fontes_do_bloco(bloco, arq) if self.gates_componentes else None)
                                passou_interno = bool((ex_interno.relatorio or {}).get("passed"))
                                self._log({"evento": "candidato_interno_executado", "bloco": bloco["name"],
                                           "arquivo": candidato.relative_to(self.pasta).as_posix(),
                                           "codigo": ex_interno.codigo, "passou": passou_interno,
                                           "segundos": ex_interno.segundos,
                                           "relatorio": ex_interno.json_path.relative_to(self.pasta).as_posix()})
                                if not passou_interno:
                                    raise ErroPlanoTeste("candidato interno isolado falhou na simulacao")
                                oficial = (self.sessao / "testes_casos" / bloco["name"] / "internos" /
                                            candidato.name)
                                oficial.parent.mkdir(parents=True, exist_ok=True)
                                shutil.copyfile(candidato, oficial)
                                self.relatar(f"  caso interno {casos_internos + 1}: APROVADO "
                                              f"({ex_interno.segundos:.1f} s)")
                                rejeicao_plano_interno = ""
                                replanejamentos_internos = 0
                            except ErroPlanoTeste as e:
                                replanejamentos_internos += 1
                                rejeicao_plano_interno = str(e)
                                self._log({"evento": "plano_teste_rejeitado", "bloco": bloco["name"],
                                           "camada": "interna", "motivo": rejeicao_plano_interno,
                                           "tentativa": replanejamentos_internos})
                                self.relatar(f"  plano interno rejeitado; replanejando "
                                              f"({replanejamentos_internos}/3) ...")
                                if replanejamentos_internos >= 3:
                                    raise ErroGeracao(
                                        f"replanejamento interno esgotado em {bloco['file']}: "
                                        f"{rejeicao_plano_interno}")
                            continue
                        internos_concluidos = True
                        self._log({"evento": "teste_interno_aprovado", "bloco": bloco["name"],
                                   "arquivo": teste_atual.relative_to(self.pasta).as_posix(),
                                   "casos": casos_internos})
                        self.relatar(f"  integracao interna {bloco['name']:<4} COMPLETE: "
                                      f"{casos_internos} caso(s); iniciando camada publica ...")
                        indice = 0
                        continue
                    if teste_atual == teste and not expansao_concluida:
                        if pendentes_publicos:
                            self.relatar("  candidato publico pendente tem prioridade; "
                                          "adiando novo planejamento ...")
                            indice += 1
                            continue
                        if not inventario_feito:
                            self._inventariar_hierarquia(bloco, arq)
                            inventario_feito = True
                        if not internos_concluidos:
                            if not interno_agendado:
                                try:
                                    caminhos = json.loads((self.sessao / "hierarquia" /
                                                          f"{bloco['name']}.json").read_text(
                                                              encoding="utf-8")).get("paths", [])
                                except (OSError, json.JSONDecodeError, AttributeError):
                                    caminhos = []
                                interno = self._escrever_teste_interno(bloco, arq, caminhos)
                                if interno is None:
                                    internos_concluidos = True
                                else:
                                    testes.insert(indice + 1, interno)
                                    interno_agendado = True
                            if not internos_concluidos:
                                indice += 1
                                continue
                        if parallel_testes_efetivo > 1:
                            casos_publicos = (max(0, len(self._testes_cocotb(
                                teste.read_text(encoding="utf-8", errors="replace"))) - 1) +
                                len(self._casos_publicos_isolados(bloco)))
                            try:
                                planos = self._decidir_lote_expansao(
                                    bloco, teste_atual, tamanho=parallel_testes_efetivo,
                                    rejeicao_anterior=rejeicao_plano_publico,
                                    casos_aprovados=casos_publicos,
                                    contexto_suite=self._contexto_publico_isolado(bloco, teste))
                            except ErroPlanoTeste as erro:
                                replanejamentos_publicos += 1
                                rejeicao_plano_publico = str(erro)
                                self._log({"evento": "lote_incremental_rejeitado", "bloco": bloco["name"],
                                           "motivo": rejeicao_plano_publico,
                                           "tentativa": replanejamentos_publicos})
                                self.relatar(f"  lote incremental invalido; replanejando "
                                              f"({replanejamentos_publicos}/3): {erro}")
                                if replanejamentos_publicos >= 3:
                                    usados += 1
                                    replanejamentos_publicos = 0
                                    self.relatar("  tres lotes invalidos; escalando o plano de cobertura ...")
                                continue
                            if planos is None:
                                expansao_concluida = True
                                self._log({"evento": "testbench_expansao_concluida",
                                            "bloco": bloco["name"],
                                            "arquivo": teste_atual.relative_to(self.pasta).as_posix(),
                                           "casos_adicionados": casos_publicos,
                                           "motivo": "modelo"})
                                self.relatar(f"  cobertura {bloco['name']:<13} COMPLETE: "
                                              f"{1 + casos_publicos} caso(s) aprovados")
                                indice += 1
                                continue
                            if casos_publicos >= self.max_casos_teste:
                                expansao_concluida = True
                                self._log({"evento": "testbench_expansao_concluida",
                                           "bloco": bloco["name"],
                                           "arquivo": teste_atual.relative_to(self.pasta).as_posix(),
                                           "casos_adicionados": casos_publicos,
                                           "motivo": "orcamento"})
                                self.relatar(f"  cobertura {bloco['name']:<13} ORÇAMENTO: "
                                              f"{casos_publicos}/{self.max_casos_teste} incremento(s) "
                                              "aprovado(s); prosseguindo para o próximo portão")
                                indice += 1
                                continue
                            lote_incremental += 1
                            self.relatar(f"  lote {lote_incremental} planejado: {len(planos)} candidato(s)")
                            for numero, plano in enumerate(planos, 1):
                                self.relatar(f"    - {self._resumo_plano_incremental(plano)}")
                                self._registrar_plano_incremental(
                                    bloco, camada="publica", numero=casos_publicos + numero,
                                    plano=plano)
                            mesclados, reprovados = self._ampliar_lote_paralelo(
                                bloco, teste_atual, planos, arq, lote_incremental)
                            if not mesclados:
                                lotes_paralelos_sem_aprovacao += 1
                                rejeicao_plano_publico = (
                                    "The previous parallel batch produced no executable passing candidate. "
                                    "Choose different legal, independent coverage gaps.")
                                if lotes_paralelos_sem_aprovacao >= 3:
                                    parallel_testes_efetivo = 1
                                    self._log({"evento": "lotes_paralelos_rebaixados_para_sequencial",
                                               "bloco": bloco["name"], "lotes_sem_aprovacao":
                                               lotes_paralelos_sem_aprovacao})
                                    self.relatar("  tres lotes paralelos sem aprovacao; "
                                                  "continuando expansao sequencial para "
                                                  f"{bloco['name']} ...")
                            else:
                                lotes_paralelos_sem_aprovacao = 0
                                testes.extend(mesclados)
                            if reprovados:
                                pendentes_publicos.extend(reprovados)
                                testes.insert(indice + 1, reprovados[0])
                                self._log({"evento": "candidatos_pendentes_priorizados",
                                           "bloco": bloco["name"], "lote": lote_incremental,
                                           "arquivos": [p.relative_to(self.pasta).as_posix()
                                                        for p in reprovados]})
                                self.relatar(f"  lote {lote_incremental}: {len(reprovados)} candidato(s) "
                                              "pendente(s); triando antes do proximo lote ...")
                                indice += 1
                            # Se houve merge, a próxima volta executa a suíte oficial
                            # combinada; se não houve, pede um novo lote sobre a mesma base.
                            continue
                        # O limite é da suíte que está efetivamente aprovada/
                        # em avaliação, não do histórico de candidatos
                        # posteriormente revertidos ou de uma execução antiga.
                        # O primeiro teste é o smoke; os demais são incrementos.
                        casos_adicionados = (max(0, quantidade_testes - 1) +
                                             len(self._casos_publicos_isolados(bloco)))
                        if casos_adicionados >= self.max_casos_teste:
                            # O orçamento limita custo e tempo; não é uma
                            # exigência de a LLM declarar que não há mais
                            # casos imagináveis. Chegamos aqui somente após a
                            # suíte aprovada ter sido executada e sem pendente.
                            expansao_concluida = True
                            self._log({"evento": "testbench_expansao_concluida",
                                       "bloco": bloco["name"],
                                       "arquivo": teste_atual.relative_to(self.pasta).as_posix(),
                                       "casos_adicionados": casos_adicionados,
                                       "motivo": "orcamento"})
                            self.relatar(f"  cobertura {bloco['name']:<13} ORÇAMENTO: "
                                          f"{casos_adicionados}/{self.max_casos_teste} incremento(s) "
                                          "aprovado(s); prosseguindo para o próximo portão")
                            indice += 1
                            continue
                        decisao = self._decidir_expansao_testbench(
                            bloco, teste_atual, rejeicao_anterior=rejeicao_plano_publico,
                            casos_aprovados=casos_adicionados,
                            contexto_suite=self._contexto_publico_isolado(bloco, teste))
                        if decisao is not None:
                            proximo_caso, _ = decisao
                            # `restantes` é apenas uma estimativa do modelo;
                            # nunca deixe a UI prometer mais que o teto local.
                            # O modelo pode estimar quantos casos faltam, mas
                            # essa previsão muda a cada rodada e não é uma
                            # meta. Exiba apenas a capacidade local estável.
                            self.relatar(f"  cobertura {bloco['name']:<13} ADD: preparando "
                                          f"incremento {casos_adicionados + 1}/{self.max_casos_teste} ...")
                            resumo_plano = self._resumo_plano_incremental(proximo_caso)
                            self.relatar(f"    racional: {resumo_plano}")
                            self._registrar_plano_incremental(
                                bloco, camada="publica", numero=casos_adicionados + 1,
                                plano=proximo_caso)
                            self._log({"evento": "plano_teste_incremental", "bloco": bloco["name"],
                                       "camada": "publica", "resumo": resumo_plano})
                            try:
                                lote_incremental += 1
                                promovidos, reprovados = self._ampliar_lote_paralelo(
                                    bloco, teste, [proximo_caso], arq, lote_incremental)
                                if reprovados:
                                    pendentes_publicos.extend(reprovados)
                                    testes.insert(indice + 1, reprovados[0])
                                    self._log({"evento": "candidatos_pendentes_priorizados",
                                               "bloco": bloco["name"], "lote": lote_incremental,
                                               "arquivos": [p.relative_to(self.pasta).as_posix()
                                                            for p in reprovados]})
                                    self.relatar("  candidato pendente; triando antes do proximo caso ...")
                                    indice += 1
                                elif promovidos:
                                    testes.extend(promovidos)
                                    rejeicao_plano_publico = ""
                                    replanejamentos_publicos = 0
                                else:
                                    raise ErroPlanoTeste("nenhum candidato isolado passou na simulacao")
                            except ErroPlanoTeste as e:
                                replanejamentos_publicos += 1
                                rejeicao_plano_publico = str(e)
                                self._log({"evento": "plano_teste_rejeitado", "bloco": bloco["name"],
                                           "camada": "publica", "motivo": rejeicao_plano_publico,
                                           "tentativa": replanejamentos_publicos})
                                self.relatar(f"  plano publico rejeitado; replanejando "
                                              f"({replanejamentos_publicos}/3) ...")
                                if replanejamentos_publicos >= 3:
                                    if usados >= self.iteracoes:
                                        raise ErroGeracao(
                                            f"orcamento esgotado ao replanejar {bloco['file']}: "
                                            f"{rejeicao_plano_publico}")
                                    usados += 1
                                    self._log({"evento": "replanejamento_teste_escalado",
                                               "bloco": bloco["name"], "camada": "publica",
                                               "motivo": rejeicao_plano_publico,
                                               "iteracao": usados})
                                    self.relatar("  tres planos publicos recusados; escalando o plano "
                                                  "com a evidencia acumulada ...")
                                    replanejamentos_publicos = 0
                            continue
                        self.relatar(f"  cobertura {bloco['name']:<13} COMPLETE: "
                                      f"{1 + casos_adicionados} caso(s) aprovados")
                        self._log({"evento": "testbench_expansao_concluida", "bloco": bloco["name"],
                                   "arquivo": teste_atual.relative_to(self.pasta).as_posix(),
                                   "casos_adicionados": casos_adicionados})
                        expansao_concluida = True
                    indice += 1
                    continue
                # Sem uma compilação VHDL bem-sucedida, o Cocotb não chegou a
                # executar o DUT. Logo não há evidência que justifique alterar
                # o testbench: a recuperação deve corrigir as fontes VHDL que
                # o compilador apontou. Isso é independente do componente e
                # evita desperdiçar o orçamento em triagens de uma simulação
                # que nem foi elaborada.
                compilacao = rel.get("compilacao")
                if isinstance(compilacao, dict) and compilacao.get("ok") is False:
                    causa = "vhdl"
                    evidencias = str(rel.get("diagnostico") or rel.get("detail") or ex.saida)
                    self.relatar(f"  compilacao VHDL falhou: encaminhando {bloco['name']} para correcao ...")
                else:
                    causa, evidencias = self._triagem_componente(ex, bloco, teste_atual)
                # Uma assertion do Cocotb exercitou o DUT, mas o teste original
                # pode ter montado estímulo/expectativa errados. Antes de alterar
                # VHDL por essa classificação, confirme-a com um teste mínimo que
                # só conhece a spec e a interface, nunca o teste que falhou.
                if (teste_atual.parent != self.sessao / "testes_internos" and
                        causa == "vhdl" and _falha_de_assertion(ex)):
                    self.relatar(f"  confirmando falha de assertion de {bloco['name']} com diagnostico independente ...")
                    causa_confirmada, evidencias_confirmadas, ex_diagnostico, diagnostico_publico = \
                        self._resolver_ambiguidade_componente(bloco, teste_atual, arq, evidencias)
                    if causa_confirmada == "testbench" and diagnostico_publico is not None and \
                            self._promover_diagnostico_publico(bloco, diagnostico_publico, teste_atual):
                        candidatos_bloqueados_vhdl.add(teste_atual)
                        falhas_corretivas = 0
                        historico_falhas.clear()
                        correcoes_cocotb_do_candidato = 0
                        continue
                    if causa_confirmada == "ambigua":
                        self.relatar(f"  diagnostico inconclusivo: escalando {bloco['name']} para revisor de recuperacao ...")
                        causa_confirmada, evidencias_confirmadas = self._revisar_convergencia_componente(
                            bloco, teste_atual,
                            [f"### triagem original\n{evidencias}",
                             f"### diagnostico independente\n{evidencias_confirmadas}"])
                        if causa_confirmada == "mixed":
                            # Um parecer conflitante não é evidência de que o
                            # contrato normativo esteja errado. Preserve-o e
                            # recupere a implementação, cuja falha foi
                            # observada pelo simulador.
                            causa_confirmada = "vhdl"
                    causa, evidencias = causa_confirmada, evidencias_confirmadas
                    if causa == "vhdl" and ex_diagnostico is not None:
                        ex = ex_diagnostico
                if teste_atual.parent == self.sessao / "testes_internos" and causa == "spec":
                    causa = "vhdl"
                    evidencias += "\n- internal integration evidence cannot revise the normative spec"
                if causa == "spec":
                    self._mostrar_fluxo(3, f"{bloco['name']}: teste falhou ──▶ "
                                        "revisar spec ──▶ regenerar ──▶ reexecutar")
                    if usados >= self.iteracoes:
                        raise ErroGeracao(f"orcamento esgotado na revisao de {bloco['file']}")
                    usados += 1
                    self._revisar_especificacao(bloco, evidencias, arq)
                    self._escrever_bloco(bloco, arq)
                    self._invalidar_dependentes_da_especificacao(bloco, arq)
                    # A spec mudou: o smoke e a suite anterior deixam de ser
                    # autoridade e precisam nascer novamente do novo contrato.
                    teste = self._escrever_testbench(bloco)
                    testes = [teste]
                    expansao_concluida = False
                    evidencia_para_regressao = None
                    regressao_criada = False
                    indice = 0
                    continue
                if causa == "ambigua":
                    causa, evidencias, ex_diagnostico, diagnostico_publico = self._resolver_ambiguidade_componente(
                        bloco, teste_atual, arq, evidencias)
                    if causa == "testbench" and diagnostico_publico is not None and \
                            self._promover_diagnostico_publico(bloco, diagnostico_publico, teste_atual):
                        candidatos_bloqueados_vhdl.add(teste_atual)
                        falhas_corretivas = 0
                        historico_falhas.clear()
                        correcoes_cocotb_do_candidato = 0
                        continue
                    if teste_atual.parent == self.sessao / "testes_internos" and causa == "spec":
                        causa = "vhdl"
                        evidencias += "\n- internal integration evidence cannot revise the normative spec"
                    if causa == "vhdl":
                        ex = ex_diagnostico or ex
                    elif causa == "spec":
                        if usados >= self.iteracoes:
                            raise ErroGeracao(f"orcamento esgotado na revisao de {bloco['file']}")
                        usados += 1
                        self._revisar_especificacao(bloco, evidencias, arq)
                        self._escrever_bloco(bloco, arq)
                        self._invalidar_dependentes_da_especificacao(bloco, arq)
                        teste = self._escrever_testbench(bloco)
                        testes = [teste]
                        expansao_concluida = False
                        evidencia_para_regressao = None
                        regressao_criada = False
                        indice = 0
                        continue
                    elif causa == "ambigua":
                        self.relatar(f"  diagnostico inconclusivo: escalando {bloco['name']} para revisor de recuperacao ...")
                        causa, evidencias = self._revisar_convergencia_componente(
                            bloco, teste_atual,
                            [f"### triagem original\n{evidencias}",
                             "### diagnostico independente\nnenhuma classificacao conclusiva"])
                        if causa == "mixed":
                            causa = "vhdl"
                        if teste_atual.parent == self.sessao / "testes_internos" and causa == "spec":
                            causa = "vhdl"
                            evidencias += "\n- internal integration evidence cannot revise the normative spec"
                        if causa == "spec":
                            if usados >= self.iteracoes:
                                raise ErroGeracao(f"orcamento esgotado na revisao de {bloco['file']}")
                            usados += 1
                            self._revisar_especificacao(bloco, evidencias, arq)
                            self._escrever_bloco(bloco, arq)
                            self._invalidar_dependentes_da_especificacao(bloco, arq)
                            teste = self._escrever_testbench(bloco)
                            testes = [teste]
                            expansao_concluida = False
                            evidencia_para_regressao = None
                            regressao_criada = False
                            indice = 0
                            continue
                if causa not in ("vhdl", "testbench"):
                    raise ErroGeracao(f"causa de triagem invalida para {bloco['file']}: {causa}")
                if causa == "testbench":
                    candidatos_bloqueados_vhdl.add(teste_atual)
                elif teste_atual in candidatos_bloqueados_vhdl:
                    causa = "testbench"
                    evidencias += ("\n- A prior independent convergence review classified this "
                                   "candidate as a testbench issue; VHDL correction is blocked.")
                    self._log({"evento": "vhdl_bloqueado_por_revisao_testbench",
                               "bloco": bloco["name"],
                               "testbench": teste_atual.relative_to(self.pasta).as_posix()})
                tabela_falhas = tabela_falhas_cocotb(
                    str((ex.relatorio or {}).get("diagnostico") or ex.saida),
                    teste_atual.read_text(encoding="utf-8", errors="replace"))
                falhas_corretivas += 1
                historico_falhas.append(f"### {causa}\n{evidencias[:1800]}\n\n{tabela_falhas}")
                if falhas_corretivas >= 2:
                    causa, evidencias = self._revisar_convergencia_componente(
                        bloco, teste_atual, historico_falhas)
                    falhas_corretivas = 0
                    historico_falhas.clear()
                    if (teste_atual.parent == self.sessao / "testes_internos" and
                            causa in ("spec", "mixed")):
                        causa = "vhdl"
                        evidencias += "\n- internal integration evidence cannot revise the normative spec"
                    if causa == "mixed":
                        # Não deixe um revisor indeciso alterar o contrato.
                        # Há uma falha concreta de execução a recuperar, por
                        # isso o próximo passo é VHDL sob a spec congelada.
                        causa = "vhdl"
                    if causa == "spec":
                        self._mostrar_fluxo(3, f"{bloco['name']}: falhas repetidas ──▶ "
                                            "revisor de convergencia ──▶ revisar spec ──▶ reexecutar")
                        if usados >= self.iteracoes:
                            raise ErroGeracao(f"orcamento esgotado na revisao de {bloco['file']}")
                        usados += 1
                        self._revisar_especificacao(bloco, evidencias, arq)
                        self._escrever_bloco(bloco, arq)
                        self._invalidar_dependentes_da_especificacao(bloco, arq)
                        teste = self._escrever_testbench(bloco)
                        testes = [teste]
                        expansao_concluida = False
                        evidencia_para_regressao = None
                        regressao_criada = False
                        indice = 0
                        continue
                if causa == "testbench":
                    candidato_publico = (teste_atual != teste and
                                          (self.sessao / "testes_candidatos") in teste_atual.parents)
                    if candidato_publico and correcoes_cocotb_do_candidato >= 3:
                        # O candidato já recebeu o máximo de correções Python
                        # permitido e a revisão causal proibiu VHDL. Descarte
                        # esta hipótese; não a transforme em alteração da CPU.
                        if teste_atual in testes:
                            testes.remove(teste_atual)
                        candidatos_bloqueados_vhdl.discard(teste_atual)
                        replanejamentos_publicos += 1
                        rejeicao_plano_publico = (
                            "The public candidate remained invalid after three Cocotb corrections; "
                            "an independent review classified it as testbench, so it cannot authorize "
                            f"VHDL. Choose a different focal case. Evidence:\n{evidencias[:3000]}")
                        self._log({"evento": "candidato_rejeitado_testbench", "bloco": bloco["name"],
                                   "testbench": teste_atual.relative_to(self.pasta).as_posix(),
                                   "motivo": rejeicao_plano_publico})
                        self.relatar("  candidato publico descartado após tres correcoes Cocotb; "
                                      "VHDL permanece inalterado")
                        correcoes_cocotb_do_candidato = 0
                        indice = 0
                        continue
                    if correcoes_cocotb_do_candidato and not candidato_publico:
                        aprovado = suites_aprovadas.get(teste_atual)
                        quantidade_aprovada = (len(self._testes_cocotb(aprovado))
                                               if aprovado is not None else quantidade_testes)
                        if (teste_atual == teste and aprovado is not None and
                                quantidade_testes > quantidade_aprovada):
                            # A expansão foi executada, recebeu uma correção
                            # Cocotb e continua falhando. Ela não é uma base
                            # válida para outra edição: restaure o snapshot e
                            # peça um novo plano focal, com a falha real.
                            teste_atual.write_text(aprovado, encoding="utf-8")
                            replanejamentos_publicos += 1
                            rejeicao_plano_publico = (
                                "A expansão candidata executou mas continuou reprovada após uma "
                                "correção Cocotb. Não repita seu estímulo/oráculo; proponha outro "
                                f"caso focal. Evidência:\n{evidencias[:3000]}")
                            self._log({"evento": "candidato_teste_revertido", "bloco": bloco["name"],
                                       "camada": "publica", "motivo": rejeicao_plano_publico,
                                       "tentativa": replanejamentos_publicos})
                            self.relatar("  candidato publico ainda falha apos correcao; "
                                          "revertendo e replanejando ...")
                            if replanejamentos_publicos < 3:
                                correcoes_cocotb_do_candidato = 0
                                continue
                            if usados >= self.iteracoes:
                                raise ErroGeracao(
                                    f"orcamento esgotado ao replanejar {bloco['file']}: "
                                    f"{rejeicao_plano_publico}")
                            usados += 1
                            self._log({"evento": "replanejamento_teste_escalado",
                                       "bloco": bloco["name"], "camada": "publica",
                                       "motivo": rejeicao_plano_publico,
                                       "iteracao": usados})
                            self.relatar("  tres candidatos publicos revertidos; escalando o plano "
                                          "com a evidencia acumulada ...")
                            replanejamentos_publicos = 0
                            correcoes_cocotb_do_candidato = 0
                            continue
                        # O smoke (ou uma regressão) não tem snapshot anterior
                        # a que voltar. A segunda falha é evidência residual do
                        # DUT e deve ir para reparo VHDL, não para outro loop
                        # de edição do mesmo Python.
                        causa = "vhdl"
                    if causa == "testbench":
                        correcoes_cocotb_do_candidato += 1
                        self._mostrar_fluxo(3, f"{bloco['name']}: teste falhou ──▶ "
                                            "triagem ──▶ corrigir Cocotb ──▶ reexecutar")
                        self.relatar(f"  triagem: corrigindo o testbench de {bloco['name']} (nao o VHDL) ...")
                        try:
                            testes[indice] = self._corrigir_testbench(
                                bloco, teste_atual, evidencias, tabela_falhas)
                        except ErroPlanoTeste as e:
                            aprovado = suites_aprovadas.get(teste_atual)
                            if teste_atual == teste and aprovado is not None and \
                                    len(self._testes_cocotb(aprovado)) < quantidade_testes:
                                teste_atual.write_text(aprovado, encoding="utf-8")
                                rejeicao_plano_publico = str(e)
                                replanejamentos_publicos += 1
                                self._log({"evento": "candidato_teste_revertido", "bloco": bloco["name"],
                                           "camada": "publica", "motivo": rejeicao_plano_publico,
                                           "tentativa": replanejamentos_publicos})
                                self.relatar("  candidato publico revertido; replanejando a partir da suite aprovada ...")
                                if replanejamentos_publicos < 3:
                                    continue
                            raise
                        continue
                if usados >= self.iteracoes:
                    raise ErroGeracao(f"orcamento esgotado no testbench de {bloco['file']}")
                usados += 1
                alvo, evidencia = self._evidencia_componente(ex, bloco, arquivos)
                evidencia += self._orientacao_interna_para_correcao(bloco, evidencia)
                if teste_atual == teste and evidencia_para_regressao is None:
                    # E a evidencia que originou a regressao; nao sera alterada
                    # mesmo que o VHDL ou os outros testes mudem depois.
                    evidencia_para_regressao = evidencia
                self.relatar(f"  iteracao {usados}/{self.iteracoes}: corrigindo {alvo} pelo teste de componente ...")
                self._mostrar_fluxo(3, f"{bloco['name']}: teste falhou ──▶ "
                                    "triagem ──▶ corrigir VHDL ──▶ reexecutar")
                novo = self._reescrever(alvo, evidencia, arq, None)
                if novo is not None:
                    self._escrever(alvo, novo)
                    if alvo == bloco["file"] and self.testes_internos and bloco.get("depends_on"):
                        # A lista VPI pertence à versão elaborada do DUT. Uma
                        # reescrita VHDL pode remover/renomear sinais; nenhum
                        # diagnóstico interno anterior pode ser reutilizado
                        # como se observasse a nova hierarquia.
                        inventario = self.sessao / "hierarquia" / f"{bloco['name']}.json"
                        inventario.unlink(missing_ok=True)
                        testes[:] = [t for t in testes
                                     if t.parent != self.sessao / "testes_internos" and
                                     not (self.sessao / "testes_casos" / bloco["name"] /
                                          "internos") in t.parents]
                        inventario_feito = False
                        internos_concluidos = False
                        interno_agendado = False
                        self._log({"evento": "hierarquia_interna_invalidada", "bloco": bloco["name"],
                                   "motivo": "fonte VHDL reescrita"})
                        self.relatar(f"  VHDL de {bloco['name']} mudou; reinventariando diagnosticos internos ...")
                    # Uma correcao pode regredir qualquer caso ja aprovado.
                    indice = 0
        return usados

    def _gerar_com_portoes(self, arq: dict) -> int:
        """Congela contratos globais antes de escrever e testar qualquer VHDL."""
        usados = 0
        self._mostrar_fluxo(2)
        self.relatar(f"{self._fase(2)} definindo contratos semanticos de todos os blocos ...")

        # Interfaces e responsabilidades vêm da arquitetura validada; logo,
        # nenhum VHDL é necessário para estabelecer a especificação. Criar
        # todos os contratos primeiro permite que a revisão da CPU detecte e
        # corrija relações entre dependências antes de uma implementação ou
        # suíte Cocotb ser produzida.
        for k, bloco in enumerate(arq["blocks"], start=1):
            deps = ", ".join(bloco.get("depends_on", [])) or "nenhuma"
            self.relatar(f"  contrato {k}/{len(arq['blocks'])}: {bloco['name']} "
                           f"(dependencias: {deps})")
            self._escrever_especificacao(bloco, arq)

        self.relatar("  revisando consistencia semantica global antes da implementacao ...")
        for bloco in arq["blocks"]:
            self._validar_especificacao_por_agente(bloco, arq)

        if self._dependencias_semanticas_revisadas:
            # Nenhuma fonte existe nesta fase: contratos revisados já serão
            # consumidos pela primeira escrita abaixo, sem retrabalho.
            revisadas = sorted(self._dependencias_semanticas_revisadas)
            self._dependencias_semanticas_revisadas = set()
            self._log({"evento": "contratos_dependencias_reconciliados",
                       "dependencias": revisadas})
        self._log({"evento": "contratos_semanticos_congelados",
                   "blocos": [bloco["name"] for bloco in arq["blocks"]]})
        self.relatar("  contratos semanticos consistentes; iniciando implementacao VHDL ...")

        for k, bloco in enumerate(arq["blocks"], start=1):
            deps = ", ".join(bloco.get("depends_on", [])) or "nenhuma"
            self.relatar(f"  portao {k}/{len(arq['blocks'])}: {bloco['name']} "
                          f"(dependencias: {deps})")
            self._escrever_bloco(bloco, arq, k, len(arq["blocks"]))
            usados = self._testar_componentes(arq, usados, [bloco])
            self._congelar_bloco(bloco)
        return usados

    def _validar(self, rotulo: str, etapa: str, casos: list[str] | None) -> Execucao:
        o_que = f"suite oficial {etapa.upper()}"
        if casos:
            o_que = f"fumaca oficial ({', '.join(casos)})"
        self.relatar(f"  spec-riscv-test {rotulo}: {o_que} ...")
        ex = self.executor.rodar(
            self.pasta, json_saida=self.sessao / "spec-riscv-test" / rotulo / "report.json",
            workdir=self.sessao / "sim" / rotulo, build_root=self.sessao / "build",
            casos=casos, etapa=etapa)
        p = placar_de(ex)
        self._log({"evento": "spec-riscv-test", "rotulo": rotulo, "etapa": etapa,
                   "casos": casos, "comando": ex.comando, "codigo": ex.codigo,
                   "segundos": ex.segundos, "placar": p.texto(),
                   "veredito": p.veredito,
                   "relatorio": ex.json_path.relative_to(self.pasta).as_posix()})
        if ex.relatorio is None:
            raise ErroGeracao(
                f"spec-riscv-test nao gerou report.json (codigo {ex.codigo}); problema de "
                f"ambiente, nao da CPU:\n{ex.saida[-1500:]}")
        relatorio = ex.relatorio
        if relatorio.get("kind") in {"environment", "selection", "program_build", "elf", "elf_contract"}:
            raise ErroGeracao(
                f"spec-riscv-test falhou antes de julgar a CPU: {relatorio.get('message', 'erro de ambiente')}. "
                f"{relatorio.get('fix', '')}".strip())
        self.relatar(f"  spec-riscv-test {rotulo:<16} {p.texto():<16} ({ex.segundos} s)")
        return ex

    def _objetivo(self, etapa: str, ex: Execucao) -> bool:
        p = placar_de(ex)
        if casos := (ex.relatorio or {}).get("executed"):
            return p.compilou and p.passou == casos
        if etapa == "fumaca":
            return p.compilou
        return p.veredito == "aprovado"

    def _erros_dos_logs(self, ex: Execucao) -> list[dict]:
        """Erros do GHDL deixados pelo wrapper oficial na sessão."""
        workdir = self.sessao / "sim" / ex.json_path.parent.name
        erros: list[dict] = []
        for log in sorted(workdir.rglob("build.log")):
            erros += erros_do_log(log.read_text(encoding="utf-8", errors="replace"))
        return erros

    def _linha_do_fonte(self, arquivo: str, linha: int) -> str:
        texto = self._ler(arquivo).splitlines()
        return texto[linha - 1].strip() if 0 < linha <= len(texto) else ""

    def _evidencia(self, ex: Execucao, arquivos: list[str]) -> tuple[str | None, str]:
        """(arquivo a corrigir, se o GHDL ja o apontou; evidencia em texto)."""
        rel = ex.relatorio or {}
        if "status" in rel:
            if rel.get("kind") == "vhdl_compile":
                erros = rel.get("errors") or self._erros_dos_logs(ex)
                por_nome = {PurePosixPath(a).name: a for a in arquivos}
                linhas = [f"{_nome_base(str(e.get('file', '?')))}:{e.get('line', '?')}:"
                          f"{e.get('column', '?')}: {e.get('message', '')}" for e in erros[:12]]
                alvo = next((por_nome.get(_nome_base(str(e.get("file", "")))) for e in erros
                              if _nome_base(str(e.get("file", ""))) in por_nome), None)
                return self._com_contrato(alvo, "GHDL compilation failed:\n" + "\n".join(linhas), arquivos)
            falhas = [r for r in rel.get("results", []) if r.get("status") != "passed"]
            if not falhas:
                falhas = [rel]
            texto = "Official riscv-tests failures:\n" + "\n".join(
                f"- {f.get('test', '?')}: {f.get('message', '')}; PC={f.get('pc', '?')}; "
                f"cycle={f.get('cycle', '?')}\n  {json.dumps(f.get('official_case', {}), ensure_ascii=False)[:1200]}"
                for f in falhas[:6])
            return self._com_contrato(None, texto, arquivos)
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
            corpo = [str(diag or c.get("detail", ""))[:400]]
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
        avisos = ct.verificar_contrato({a: self._ler(a) for a in arquivos})
        if not avisos:
            return alvo, texto
        texto += ("\n\nContract check (static inspection of the text; a suggestion):\n"
                  + "\n".join(f"- {a}: {m}" for a, m in avisos))
        return alvo or avisos[0][0], texto

    def _escolher(self, evidencia: str, arq: dict) -> tuple[str, str]:
        """Localiza um defeito funcional vendo todas as implementações atuais."""
        arquivos = [b["file"] for b in arq["blocks"]]
        plano = "\n".join(f"- {b['file']}: {b['responsibility']}" for b in arq["blocks"])
        fontes = "\n\n".join(
            f"### {arquivo}\n```vhdl\n{self._ler(arquivo)}\n```" for arquivo in arquivos)
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                "Act as a VHDL integration debugger. Inspect EVERY complete source file below; "
                "do not infer a location from the component responsibility alone. The validator "
                "evidence may name a symptom, while the defect can be in a connected component.\n\n"
                f"Validator evidence:\n{evidencia}\n\nComponent responsibilities:\n{plano}\n\n"
                f"Complete current VHDL sources:\n{fontes}\n\n"
                "Which ONE file most likely contains the root cause? Cite one or more exact, "
                "1-based line numbers in that file and explain the concrete faulty VHDL behavior. "
                f"Answer ONLY JSON: {{\"file\": one of {arquivos}, \"reason\": \"...\", "
                "\"lines\": [positive integers]}}.")},
        ]
        self.relatar("  escolhendo o arquivo a corrigir ...")
        r = self._chamar("escolha", "-", mensagens, schema=_schema_escolha(arquivos))
        try:
            resposta = extrair_json(r.texto)
            escolhido = str(resposta.get("file", ""))
            linhas = [int(linha) for linha in resposta.get("lines", [])
                      if isinstance(linha, int) and linha > 0]
            razao = str(resposta.get("reason", "")).strip()
        except (ErroLLM, AttributeError):
            escolhido, linhas, razao = "", [], ""
        if escolhido not in arquivos:
            escolhido = f"src/{ct.TOP}.vhd"
            linhas = []
            razao = "modelo nao indicou um arquivo valido; fallback para o top-level"
        total_linhas = len(self._ler(escolhido).splitlines())
        linhas = [linha for linha in linhas if linha <= total_linhas]
        diagnostico = (f"LLM localization after inspecting all VHDL sources:\n"
                       f"- selected file: {escolhido}\n"
                       f"- cited lines: {', '.join(map(str, linhas)) or '(none valid)'}\n"
                       f"- reason: {razao or '(none)'}")
        self._log({"evento": "localizacao_vhdl", "arquivo": escolhido, "linhas": linhas,
                   "razao": razao, "fontes": arquivos})
        return escolhido, diagnostico

    def _reescrever(self, alvo: str, evidencia: str, arq: dict,
                    nota: str | None, temperatura: float | None = None) -> str | None:
        nome = PurePosixPath(alvo).stem
        atual = self._ler(alvo)
        bloco = next((b for b in arq["blocks"] if b["file"] == alvo), None)
        especificacao = self._ler_especificacao(bloco) if bloco else "(no component contract)"
        integracao = ("\n\n" + self._requisito_integracao_top(arq["blocks"])
                      if alvo == f"src/{ct.TOP}.vhd" else "")
        mensagens = [
            {"role": "system", "content": self.contrato},
            {"role": "user", "content": (
                f"{self._texto_descricao()}"
                f"The CPU was run by the validator and failed.\n{evidencia}\n\n"
                + (f"NOTE: {nota}\n\n" if nota else "")
                + f"Entity declarations of the other files (keep compatible):\n"
                f"{self._declaracoes(arq['blocks'], exceto=alvo)}\n\n"
                  + f"Normative component semantic contract (do not change it):\n"
                  f"{especificacao}\n\n"
                  + integracao
                  + f"\n\nCurrent content of {alvo}:\n```vhdl\n{atual}```\n\n"
                f"Fix {alvo}. Keep the entity name and ports unless the evidence "
                f"shows that the ports themselves are wrong. Answer with the "
                f"complete corrected file in one ```vhdl block.")},
        ]
        for tentativa in (1, 2):
            r = self._chamar("correcao", alvo, mensagens, temperatura=temperatura)
            vhdl = extrair_vhdl(r.texto)
            top_ok, motivo_top = (self._integracao_top_valida(vhdl, arq)
                                  if vhdl and alvo == f"src/{ct.TOP}.vhd" else (True, ""))
            if vhdl and re.search(rf"\bentity\s+{nome}\s+is\b", vhdl, re.IGNORECASE) and top_ok:
                return None if vhdl.strip() == atual.strip() else vhdl
            mensagens += [{"role": "assistant", "content": r.texto},
                          {"role": "user", "content":
                             f"No acceptable ```vhdl block with `entity {nome} is`. {motivo_top} "
                             "Send the complete file."}]
        return None

    def _corrigir(self, arq: dict, iteracao_inicial: int = 0) -> tuple[Execucao, str, int]:
        """FR-RV-48: mede, corrige um arquivo, mede de novo; desfaz o que piora."""
        fase = 4 if self.testes_componentes else 3
        self._mostrar_fluxo(fase)
        self.relatar(f"{self._fase(fase)} validacao, investigação e correção "
                     f"(ate {self.iteracoes} rodadas)")
        etapas = [("fumaca", self.isa, [self.caso_de_fumaca()]),
                  ("suite", self.isa, None)]
        arquivos = [b["file"] for b in arq["blocks"]]
        i = 0
        atual = self._validar(etapas[0][0], etapas[0][1], etapas[0][2])
        iteracao = iteracao_inicial
        correcoes_vhdl = 0
        nota: str | None = None
        repeticoes = 0          # respostas seguidas sem mudanca efetiva
        # A fonte inicial de uma retomada pode ser diferente daquela que gerou
        # as regressões persistidas; meça-a uma vez. Depois, toda alteração é
        # medida imediatamente pelo portão pós-correção, portanto repetir os
        # mesmos Cocotbs após um rollback só desperdiçaria tempo.
        focados_medidos_para_fonte = False
        bloco_fixado: str | None = None
        falhas_do_bloco_fixado = 0
        historico_bloco_fixado: list[str] = []
        candidatos_bloco_fixado: set[str] = set()
        duracoes: list[float] = []              # segundos de cada iteracao, para a estimativa
        inicio_iteracao: float | None = None
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
            geradas_agora = self._gerar_regressoes_oficiais(atual, arq)
            foco_oficial = self._proxima_regressao_oficial(atual)
            # Na primeira medição elas são executadas pela própria geração.
            # Em uma retomada, os módulos já existem e a fonte pode ter mudado
            # desde então; meça-a uma única vez. Uma correção é sempre medida
            # logo após ser escrita, e o resultado vale também se ela for
            # desfeita, pois o rollback restaura esta mesma fonte.
            if geradas_agora:
                focados_medidos_para_fonte = True
                focados_antes_ok, evidencia_focados_antes = True, ""
            elif not focados_medidos_para_fonte:
                focados_antes_ok, evidencia_focados_antes = self._validar_regressoes_oficiais(
                    arq, iteracao + 1, {foco_oficial} if foco_oficial else set())
                focados_medidos_para_fonte = True
            else:
                focados_antes_ok, evidencia_focados_antes = True, ""
            if inicio_iteracao is not None:
                duracoes.append(time.monotonic() - inicio_iteracao)
            if duracoes:
                media = sum(duracoes) / len(duracoes)
                restantes = self.iteracoes - iteracao
                self.relatar(f"  ~{media * restantes / 60:.0f} min se usar as {restantes} "
                             f"rodadas restantes (media de {media:.0f} s por rodada)")
            inicio_iteracao = time.monotonic()
            iteracao += 1
            titulo_foco = foco_oficial or "falha oficial sem regressão focal reproduzida"
            self._definir_escopos_log(
                (f"oficial:{titulo_foco}", f"Falha oficial: {titulo_foco}"),
                (f"investigacao:{iteracao}", f"Rodada de investigação {iteracao}"))
            alvo, evidencia = self._evidencia(atual, arquivos)
            if foco_oficial:
                evidencia += (f"\n\nCURRENT FOCUSED OBJECTIVE: resolve only `{foco_oficial}` in this "
                              "iteration. Other official failures remain queued and must not cause a "
                              "rollback of a correction that resolves this objective.")
            # Uma reversão de componente é evidência diagnóstica para a
            # próxima escolha, não apenas uma nota para quem reescreverá o
            # mesmo arquivo. Assim o localizador pode trocar de componente ou
            # propor uma causa diferente em vez de repetir a tentativa.
            if nota:
                evidencia += "\n\nPREVIOUS CORRECTION FEEDBACK (must be considered):\n" + nota
            escolhido_pelo_modelo = False
            correcao_por_exploracao = False
            cpu_principal = next((b for b in arq["blocks"] if b["name"] == ct.TOP), None)
            if bloco_fixado is not None:
                alvo = bloco_fixado
                evidencia += (f"\n\nPINNED COMPONENT: `{alvo}` has a confirmed failing component-level "
                              "regression. Keep correcting this file until its complete existing Cocotb "
                              "suite passes; do not select another file.")
                self.relatar(f"  mantendo componente confirmado: {alvo} ...")
            elif foco_oficial and cpu_principal:
                caminho_exploracao, estado_exploracao = self._estado_exploracao_cpu(
                    foco_oficial, cpu_principal)
                if not estado_exploracao.get("ativado"):
                    estado_exploracao["ativado"] = True
                    self._salvar_estado_exploracao_cpu(caminho_exploracao, estado_exploracao)
                    self.relatar("  investigação adaptativa: formulando primeira hipótese causal ...")
                execucao_oficial = self._capturar_execucao_oficial_focal(
                    cpu_principal, foco_oficial, caminho_exploracao, estado_exploracao)
                evidencia += ("\n\nOFFICIAL COCOTB EXECUTION (same ELF and memory model as "
                              f"spec-riscv-test):\n{json.dumps(execucao_oficial, ensure_ascii=False)}")
                autorizada, esgotada, evidencia_exploracao, alvo_confirmado = self._explorar_cpu_superior(
                    cpu_principal, arq, foco_oficial, evidencia)
                if evidencia_exploracao:
                    evidencia += "\n\n" + evidencia_exploracao
                if esgotada:
                    self.relatar("  investigação adaptativa concluída sem nova correção autorizada")
                    self._log({"evento": "exploracao_cpu_esgotada", "foco": foco_oficial})
                    return atual, nome_etapa, iteracao
                if not autorizada:
                    self.relatar("  análise VCD concluída")
                    continue
                alvo = alvo_confirmado or cpu_principal["file"]
                correcao_por_exploracao = True
                self.relatar(f"  hipótese causal confirmada; correção autorizada em {alvo}")
            elif alvo is None:
                alvo, localizacao = self._escolher(evidencia, arq)
                evidencia += "\n\n" + localizacao
                escolhido_pelo_modelo = True
            if not focados_antes_ok:
                evidencia += "\n\n" + evidencia_focados_antes
            motivo = "escolhido pelo modelo" if escolhido_pelo_modelo else "apontado pelo GHDL/diagnostico"
            temperatura = TEMPERATURAS_NA_REPETICAO[
                min(repeticoes, len(TEMPERATURAS_NA_REPETICAO) - 1)]
            extra = f", temperatura {temperatura}" if temperatura is not None else ""
            self.relatar(f"  fronteira causal candidata: {alvo} "
                           f"({motivo}{extra}; rodada {iteracao}/{self.iteracoes})")
            self._mostrar_fluxo(fase, "falha oficial ──▶ criar testes ──▶ executar/VCD "
                                  "──▶ confirmar ou refutar hipótese")
            bloco_alvo = next((b for b in arq["blocks"] if b["file"] == alvo), None)
            if (not correcao_por_exploracao and "status" in (atual.relatorio or {}) and bloco_alvo and
                    bloco_alvo["name"] == ct.TOP and foco_oficial):
                caminho_exploracao, estado_exploracao = self._estado_exploracao_cpu(
                    foco_oficial, bloco_alvo)
                estado_exploracao["ativado"] = True
                self._salvar_estado_exploracao_cpu(caminho_exploracao, estado_exploracao)
                self.relatar("  investigação adaptativa ativada: próxima rodada formulará uma "
                             "hipótese e seu teste discriminante")
                continue
            if ("status" in (atual.relatorio or {}) and bloco_alvo and
                    bloco_alvo["name"] != ct.TOP):
                # Antes de alterar uma dependência, a hipótese de localização
                # precisa falhar em suas próprias portas. Uma falha só da CPU
                # não autoriza reescrever decoder/ALU às cegas.
                regressao = next(iter(sorted((self.sessao / "regressoes").glob(
                    f"test_{bloco_alvo['name']}_regressao_*.py"))), None)
                if regressao is None:
                    self.relatar(f"  hipotese {bloco_alvo['name']}: gerando regressao Cocotb focal ...")
                    try:
                        regressao = self._escrever_regressao(
                            bloco_alvo, evidencia,
                            len(list((self.sessao / "regressoes").glob("*.py"))) + 1)
                    except ErroGeracao as erro:
                        nota = (f"Component hypothesis testbench generation failed for "
                                f"{bloco_alvo['file']}; this is not DUT evidence: {erro}")
                        tentativa_tb = 1
                        if foco_oficial and cpu_principal:
                            caminho_estado, estado_tb = self._estado_exploracao_cpu(
                                foco_oficial, cpu_principal)
                            chave_tb = bloco_alvo["file"]
                            rejeicoes_tb = estado_tb.setdefault("component_testbench_rejections", {})
                            tentativa_tb = int(rejeicoes_tb.get(chave_tb, {}).get("attempts", 0)) + 1
                            rejeicoes_tb[chave_tb] = {"attempts": tentativa_tb,
                                                      "detail": str(erro)[-5000:]}
                            if tentativa_tb >= 3:
                                estado_tb["bloqueados"][chave_tb] = (
                                    "component testbench unavailable after three generation failures")
                                estado_tb["ativado"] = True
                            self._salvar_estado_exploracao_cpu(caminho_estado, estado_tb)
                        self._log({"evento": "regressao_componente_rejeitada",
                                   "bloco": bloco_alvo["name"], "tentativa": tentativa_tb,
                                   "motivo": str(erro)[-5000:]})
                        self.relatar(f"  hipotese {bloco_alvo['name']}: testbench inválido "
                                     f"({tentativa_tb}/3)")
                        continue
                else:
                    self.relatar(f"  hipotese {bloco_alvo['name']}: reutilizando "
                                 f"{regressao.name} ...")
                self.relatar(f"  hipotese {bloco_alvo['name']}: executando para confirmar a localizacao ...")
                ex_focal = self.executor.rodar_componente(
                    self.pasta, componente=bloco_alvo["name"], teste=regressao,
                    json_saida=self.sessao / "testes_resultados" /
                    f"it{iteracao:02d}-hipotese-{bloco_alvo['name']}.json",
                    workdir=self.sessao / "sim" / f"hipotese-it{iteracao:02d}-{bloco_alvo['name']}",
                    build_root=self.sessao / "build" / f"hipotese-it{iteracao:02d}-{bloco_alvo['name']}",
                    fontes=self._fontes_do_bloco(bloco_alvo, arq) if self.gates_componentes else None)
                rel_focal = ex_focal.relatorio or {}
                if bool((rel_focal.get("compilacao") or {}).get("ok")) and \
                        not bool(rel_focal.get("passed")) and not _falha_de_assertion(ex_focal):
                    # Erro Python/Cocotb antes de uma assertion não é falha
                    # do componente. Corrija o teste e execute-o de novo antes
                    # de sequer considerar uma alteração VHDL.
                    self.relatar(f"  hipotese {bloco_alvo['name']}: Cocotb invalido; corrigindo teste ...")
                    regressao = self._corrigir_testbench(
                        bloco_alvo, regressao,
                        str(rel_focal.get("diagnostico") or ex_focal.saida),
                        tabela_falhas_cocotb(
                            str(rel_focal.get("diagnostico") or ex_focal.saida),
                            regressao.read_text(encoding="utf-8", errors="replace")))
                    ex_focal = self.executor.rodar_componente(
                        self.pasta, componente=bloco_alvo["name"], teste=regressao,
                        json_saida=self.sessao / "testes_resultados" /
                        f"it{iteracao:02d}-hipotese-{bloco_alvo['name']}.json",
                        workdir=self.sessao / "sim" / f"hipotese-it{iteracao:02d}-{bloco_alvo['name']}",
                        build_root=self.sessao / "build" / f"hipotese-it{iteracao:02d}-{bloco_alvo['name']}",
                        fontes=self._fontes_do_bloco(bloco_alvo, arq) if self.gates_componentes else None)
                    rel_focal = ex_focal.relatorio or {}
                reproduziu = _falha_de_assertion(ex_focal)
                self._log({"evento": "hipotese_localizacao_executada",
                           "bloco": bloco_alvo["name"],
                           "arquivo": regressao.relative_to(self.pasta).as_posix(),
                           "reproduziu": reproduziu, "iteracao": iteracao,
                           "segundos": ex_focal.segundos,
                           "relatorio": ex_focal.json_path.relative_to(self.pasta).as_posix()})
                self.relatar(f"  hipotese {bloco_alvo['name']}: "
                             f"{'REPRODUZIU a falha; correcao autorizada' if reproduziu else 'nao reproduziu; correcao bloqueada'} "
                             f"({ex_focal.segundos:.1f} s)")
                if not reproduziu:
                    if bloco_fixado == bloco_alvo["file"]:
                        bloco_fixado = None
                    nota = (f"The localized component regression for {bloco_alvo['file']} did not "
                            "reproduce the reported defect. Select a different root cause; do not "
                            "modify this component without a failing port-level test.")
                    if foco_oficial and cpu_principal:
                        self._bloquear_hipotese_focal(
                            foco_oficial, cpu_principal, bloco_alvo["file"],
                            "component-level regression passed; defect not reproduced")
                    self.relatar(f"  hipotese {bloco_alvo['name']}: nao reproduziu; nao alterando VHDL")
                    continue
            antes = self._ler(alvo)
            correcoes_vhdl += 1
            self._acrescentar_escopo_log(
                f"correcao_vhdl:{correcoes_vhdl}",
                f"Correção VHDL {correcoes_vhdl} autorizada: {alvo}")
            self.relatar(f"  reescrevendo {alvo} ...")
            novo = self._reescrever(alvo, evidencia, arq, nota, temperatura)
            if novo is None:
                repeticoes += 1
                nota = (f"Your last answer for {alvo} was unusable or identical to the "
                        f"current file. Make a real change.")
                self._log({"evento": "correcao_vazia", "alvo": alvo, "iteracao": iteracao,
                           "temperatura": temperatura})
                continue
            assinatura = hashlib.sha256(novo.encode("utf-8")).hexdigest()
            if bloco_fixado == alvo and assinatura in candidatos_bloco_fixado:
                nota = (f"The proposed VHDL for {alvo} is identical to a previously rejected "
                        "candidate. Make a substantively different change addressing the component "
                        "test failure history.")
                self.relatar("  candidato VHDL repetido; recusando sem simular")
                continue
            if bloco_fixado == alvo:
                candidatos_bloco_fixado.add(assinatura)
            self._escrever(alvo, novo)
            if ("status" in (atual.relatorio or {}) and bloco_alvo and
                    bloco_alvo["name"] != ct.TOP):
                passou_bloco, falhas_bloco = self._rodar_provas_do_bloco(
                    bloco_alvo, arq, f"it{iteracao:02d}-pos-correcao")
                if not passou_bloco:
                    self._escrever(alvo, antes)
                    bloco_fixado = bloco_alvo["file"]
                    falhas_do_bloco_fixado += 1
                    historico_bloco_fixado.append(
                        f"Attempt {falhas_do_bloco_fixado} for {alvo} failed its component suite:\n"
                        f"{falhas_bloco}")
                    if falhas_do_bloco_fixado >= 3:
                        revisao = self._revisar_correcao_local(
                            bloco_alvo, regressao, historico_bloco_fixado)
                        nota = (f"Local diagnostic review after three rejected component fixes:\n"
                                f"{revisao}\n\nUse this review and make a different change.")
                        falhas_do_bloco_fixado = 0
                    else:
                        nota = (f"Your change to {alvo} was reverted because its complete existing Cocotb "
                                f"suite failed after the change:\n{falhas_bloco}")
                    self.relatar(f"  provas de {bloco_alvo['name']} falharam; alteracao desfeita")
                    continue
                if bloco_fixado == bloco_alvo["file"]:
                    bloco_fixado = None
                    falhas_do_bloco_fixado = 0
                    historico_bloco_fixado.clear()
                    candidatos_bloco_fixado.clear()
                    self.relatar(f"  provas de {bloco_alvo['name']} aprovadas; liberando proxima falha")
                cpu = next((b for b in arq["blocks"] if b["name"] == ct.TOP), None)
                if cpu:
                    passou_cpu, falhas_cpu = self._rodar_provas_do_bloco(
                        cpu, arq, f"it{iteracao:02d}-integracao")
                    if not passou_cpu:
                        self._escrever(alvo, antes)
                        nota = (f"Your change to dependency {alvo} was reverted because existing CPU "
                                f"integration tests failed:\n{falhas_cpu}")
                        self.relatar("  provas de integracao da CPU falharam; alteracao desfeita")
                        continue
            focados_ok, evidencia_focados = self._validar_regressoes_oficiais(
                arq, iteracao, {foco_oficial} if foco_oficial else set())
            focados_medidos_para_fonte = True
            if not focados_ok:
                # A aprovação final continua exigindo a regressão oficial.
                # Porém uma correção exploratória pode ser preservada como
                # degrau intermediário se avançar objetivamente a mesma prova,
                # mantiver a suíte CPU e não piorar o placar oficial completo.
                progresso = False
                detalhe_progresso = ""
                if correcao_por_exploracao and bloco_alvo and cpu_principal:
                    progresso, detalhe_progresso = self._revalidar_progresso_exploratorio(
                        cpu_principal, arq, iteracao)
                if progresso and bloco_alvo:
                    provas_ok, falhas_provas = self._rodar_provas_do_bloco(
                        bloco_alvo, arq, f"it{iteracao:02d}-progresso-parcial")
                    if provas_ok:
                        medicao_parcial = self._validar(
                            f"it{iteracao:02d}-progresso-parcial", self.isa, None)
                        if placar_de(medicao_parcial).chave() >= placar_de(atual).chave():
                            registrado = self._registrar_progresso_parcial(
                                foco_oficial or "falha-focal", cpu_principal or bloco_alvo,
                                detalhe_progresso, bloco_alvo)
                            if registrado:
                                atual = medicao_parcial
                                nota = ("The previous change was preserved as measurable intermediate "
                                        f"progress although `{foco_oficial}` still fails. {detalhe_progresso}. "
                                        "Continue from this improved source; do not undo the causal gain.")
                                self._congelar_bloco(bloco_alvo)
                                self.relatar("  progresso parcial confirmado; alteração preservada para a próxima etapa")
                                self._log({"evento": "progresso_parcial_preservado", "alvo": alvo,
                                           "iteracao": iteracao, "detalhe": detalhe_progresso,
                                           "placar": placar_de(atual).texto()})
                                focados_medidos_para_fonte = True
                                continue
                            detalhe_progresso += "; partial-progress limit reached or source already recorded"
                        detalhe_progresso += (f"; official score regressed to "
                                              f"{placar_de(medicao_parcial).texto()}")
                    else:
                        detalhe_progresso += f"; existing CPU proofs failed: {falhas_provas}"
                self._escrever(alvo, antes)
                nota = (f"Your previous change to {alvo} was reverted because it did not pass "
                        f"the focused official Cocotb regressions and had no safe measurable "
                        f"intermediate progress:\n{evidencia_focados}\n{detalhe_progresso}")
                self.relatar("  regressão oficial focada ainda falha; alteracao desfeita antes da suíte")
                self._log({"evento": "reversao_regressao_oficial_focada", "alvo": alvo,
                           "iteracao": iteracao, "evidencia": evidencia_focados})
                continue
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

    def retomar(self) -> Resultado:
        """Retoma uma sessão interrompida a partir do primeiro bloco pendente.

        A arquitetura e os contratos da própria sessão são autoridade; fontes e
        testes já aprovados não são regenerados. Esta operação requer os gates
        de componentes, pois são eles que deixam checkpoints verificáveis.
        """
        inicio = time.monotonic()
        arq_path = self.pasta / "architecture.json"
        if not self.sessao.is_dir() or not arq_path.is_file():
            raise ErroGeracao("sessao ou architecture.json ausente para retomada")
        if (self.sessao / "resultado.json").exists():
            raise ErroGeracao("a sessao ja possui resultado final; inicie uma nova geracao")
        try:
            arq = json.loads(arq_path.read_text(encoding="utf-8"))
            blocos, motivo = validar_arquitetura(arq)
        except (OSError, json.JSONDecodeError) as e:
            raise ErroGeracao(f"architecture.json invalido para retomada: {e}") from e
        if not blocos:
            raise ErroGeracao(f"architecture.json invalido para retomada: {motivo}")
        arq["blocks"] = blocos
        if not self.testes_componentes or not self.gates_componentes:
            raise ErroGeracao("retomada exige sessao criada com --testes-componentes e --gates-componentes")
        selo = self.protegidos()
        aprovados: set[str] = set()
        for registro in (self.sessao / "componentes_aprovados").glob("*.json"):
            try:
                dado = json.loads(registro.read_text(encoding="utf-8"))
                fonte = self._destino(str(dado["arquivo"]))
                if fonte.exists() and dado.get("hash_vhdl") == hash_de([fonte]):
                    aprovados.add(str(dado["bloco"]))
            except (OSError, ValueError, KeyError, json.JSONDecodeError):
                continue
        pendentes = [b for b in arq["blocks"] if b["name"] not in aprovados]
        self._log({"evento": "retomada", "blocos_aprovados": sorted(aprovados),
                   "bloco_inicial": pendentes[0]["name"] if pendentes else None})
        self.relatar(f"retomando sessao: {len(aprovados)} bloco(s) aprovados; "
                      f"inicio em {pendentes[0]['name'] if pendentes else 'spec-riscv-test'}")
        usados = 0
        for bloco in pendentes:
            if not self._caminho_especificacao(bloco).exists():
                self._escrever_especificacao(bloco, arq)
            # Uma sessão pode ter sido interrompida durante a revisão do
            # contrato, antes da primeira escrita VHDL. Revalide esse contrato
            # pendente no código atual; não o transforme em fonte apenas por
            # existir no disco.
            if not self._destino(bloco["file"]).exists():
                self._validar_especificacao_por_agente(bloco, arq)
                usados = self._regerar_dependencias_semanticas_revisadas(arq, usados)
            if not self._destino(bloco["file"]).exists():
                self._escrever_bloco(bloco, arq)
            usados = self._testar_componentes(arq, usados, [bloco], reutilizar_testes=True)
            self._congelar_bloco(bloco)
        ultima, etapa, iteracoes = self._corrigir(arq, usados)
        if self.protegidos() != selo:
            raise ErroIntegridade("um arquivo protegido mudou durante a retomada; o veredito foi recusado")
        final = ultima if etapa == "suite" else self._validar("final", self.isa, None)
        p = placar_de(final)
        atingido = p.veredito == "aprovado"
        resultado = Resultado(p.veredito or "desconhecido", atingido, p, iteracoes,
                              self._chamadas, self._tokens[0], self._tokens[1],
                              round(time.monotonic() - inicio, 1), self.sessao, final.json_path)
        resumo = {"veredito": resultado.veredito, "objetivo_atingido": atingido,
                  "placar": p.texto(), "iteracoes": iteracoes, "chamadas": resultado.chamadas,
                  "tokens_entrada": resultado.tokens_entrada, "tokens_saida": resultado.tokens_saida,
                  "segundos": resultado.segundos, "provedor": self.cliente.provedor,
                  "modelo": self.cliente.modelo, "microarquitetura": self.microarquitetura,
                  "isa": self.isa, "retomada": True,
                  "relatorio": final.json_path.relative_to(self.pasta).as_posix()}
        (self.sessao / "resultado.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False) + "\n",
                                                      encoding="utf-8")
        self._log({"evento": "fim", **resumo})
        return resultado

    def gerar(self) -> Resultado:
        inicio = time.monotonic()
        self._preparar_pasta()
        selo = self.protegidos()
        self._log({"evento": "inicio", "pasta": str(self.pasta),
                   "isa": self.isa, "provedor": self.cliente.provedor,
                     "modelo": self.cliente.modelo, "executor": self.executor.nome,
                     "iteracoes": self.iteracoes,
                     "tentativas_revisao_semantica": self.tentativas_revisao_semantica,
                      "microarquitetura": self.microarquitetura,
                      "testes_componentes": self.testes_componentes,
                     "testes_internos": self.testes_internos,
                    "regressoes_componentes": self.regressoes_componentes,
                    "gates_componentes": self.gates_componentes,
                   "exemplo": str(self.exemplo) if self.exemplo else None,
                   "descricao": self.descricao})

        self._resumir_cpu_proposta()
        instrucoes = self._inventariar_instrucoes()
        arq = self._planejar(instrucoes)
        arq["instructions"] = instrucoes
        (self.pasta / "architecture.json").write_text(
            json.dumps(arq, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        arquivos = [b["file"] for b in arq["blocks"]]
        usadas = 0
        if self.gates_componentes:
            usadas = self._gerar_com_portoes(arq)
        else:
            self._mostrar_fluxo(2)
            self.relatar(f"{self._fase(2)} implementando blocos com contratos semanticos ...")
            for k, bloco in enumerate(arq["blocks"], start=1):
                self._escrever_especificacao(bloco, arq)
                self._validar_especificacao_por_agente(bloco, arq)
                self._escrever_bloco(bloco, arq, k, len(arq["blocks"]))
        if self.testes_componentes and not self.gates_componentes:
            usadas = self._compilar_antes_dos_testes(arq, usadas)
            usadas = self._testar_componentes(arq, usadas)
        ultima, etapa, iteracoes = self._corrigir(arq, usadas)

        # FR-RV-49: nada que o julga pode ter mudado enquanto a CPU era gerada
        if self.protegidos() != selo:
            self._log({"evento": "integridade", "ok": False})
            raise ErroIntegridade(
                "um arquivo de spec-riscv-test/ ou uma fonte fornecida mudou durante a "
                "geracao; o veredito foi recusado")
        # O veredito vem da suite oficial completa, sem --tests.
        if etapa == "suite":
            self._mostrar_fluxo(5 if self.testes_componentes else 4)
            self.relatar(f"{self._fase(5 if self.testes_componentes else 4)} veredito: a ultima "
                          "execucao ja foi a suite oficial completa")
            final = ultima
        else:
            self._mostrar_fluxo(5 if self.testes_componentes else 4)
            self.relatar(f"{self._fase(5 if self.testes_componentes else 4)} veredito")
            final = self._validar("final", self.isa, None)
        p = placar_de(final)
        atingido = p.veredito == "aprovado"
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
                    "microarquitetura": self.microarquitetura, "isa": self.isa,
                    "testes_componentes": self.testes_componentes,
                    "regressoes_componentes": self.regressoes_componentes,
                   "gates_componentes": self.gates_componentes,
                  "exemplo": str(self.exemplo) if self.exemplo else None,
                  "descricao": self.descricao,
                  "relatorio": final.json_path.relative_to(self.pasta).as_posix()}
        (self.sessao / "resultado.json").write_text(
            json.dumps(resumo, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        self._log({"evento": "fim", **resumo})
        return resultado
