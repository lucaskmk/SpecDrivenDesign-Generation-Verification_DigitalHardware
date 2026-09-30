#!/usr/bin/env python3
"""Configuracao do gerador: arquivo `.env`, variaveis de ambiente e defaults.

REQ: FR-RV-46 (provedor e modelo escolhidos por configuracao, sem mudar
codigo).

Tudo o que muda de uma maquina para outra entra por variavel de ambiente, e
o `.env` da raiz (o mesmo da trilha A, ver `.env.example`) so preenche o que
o ambiente ainda nao definiu -- o ambiente sempre vence o arquivo.

    RVGEN_PROVEDOR       ollama | openrouter             (padrao: ollama)
    RVGEN_MODELO         nome do modelo                  (padrao: perfil pela VRAM)
    OLLAMA_HOST          endereco do servidor Ollama     (padrao: candidatos)
    OPENROUTER_API_KEY   chave do provedor externo
    SPECHDL_LLM_MODEL    modelo externo padrao           (o mesmo da trilha A)
    RVGEN_NUM_CTX        janela de contexto no Ollama    (padrao: 16384)
    RVGEN_TIMEOUT        segundos por chamada ao modelo  (padrao: 900)
    RVGEN_EXECUTOR       auto | local | docker           (padrao: auto)
    RVGEN_IMAGEM_DOCKER  imagem do validador             (padrao: spechdl-toolchain)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import MutableMapping

__all__ = [
    "Config",
    "ErroConfig",
    "carregar_env",
    "ler_config",
    "REPO_ROOT",
    "PROVEDORES",
    "EXECUTORES",
    "OPENROUTER_URL",
    "MODELO_EXTERNO_PADRAO",
    "IMAGEM_DOCKER_PADRAO",
]

REPO_ROOT = Path(__file__).resolve().parent.parent

PROVEDORES = ("ollama", "openrouter")
EXECUTORES = ("auto", "local", "docker")

OPENROUTER_URL = "https://openrouter.ai/api/v1"
# O mesmo default de `.env.example` e de `legado/scripts/llm_playground.py`:
# quem ja configurou a trilha A nao precisa configurar nada de novo.
MODELO_EXTERNO_PADRAO = "openai/gpt-5.6-luna"
IMAGEM_DOCKER_PADRAO = "spechdl-toolchain"


class ErroConfig(ValueError):
    """Valor de configuracao invalido, com o nome da variavel que o trouxe."""


def carregar_env(caminho: Path | None = None,
                 ambiente: MutableMapping[str, str] | None = None) -> list[str]:
    """Le `KEY=VALUE` de um `.env` sem sobrescrever o que ja esta definido.

    Devolve as chaves que o arquivo efetivamente preencheu. Linhas vazias,
    comentarios (`#`) e o prefixo `export ` sao aceitos; aspas simples ou
    duplas em volta do valor sao removidas.
    """
    alvo = os.environ if ambiente is None else ambiente
    arquivo = caminho if caminho is not None else REPO_ROOT / ".env"
    if not arquivo.is_file():
        return []
    carregadas: list[str] = []
    for linha in arquivo.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        if linha.startswith("export "):
            linha = linha[len("export "):]
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.strip()
        if len(valor) >= 2 and valor[0] == valor[-1] and valor[0] in "\"'":
            valor = valor[1:-1]
        if chave and chave not in alvo and valor:
            alvo[chave] = valor
            carregadas.append(chave)
    return carregadas


@dataclass(frozen=True)
class Config:
    """A configuracao efetiva de uma execucao do gerador."""

    provedor: str
    modelo: str | None            # None => perfil pela VRAM (ollama) ou padrao externo
    ollama_host: str | None
    openrouter_key: str | None
    openrouter_url: str
    modelo_externo: str
    num_ctx: int
    temperatura: float
    timeout_s: float
    executor: str
    imagem_docker: str


def _int(ambiente: MutableMapping[str, str], nome: str, padrao: int) -> int:
    texto = ambiente.get(nome)
    if not texto:
        return padrao
    try:
        valor = int(texto)
    except ValueError:
        raise ErroConfig(f"{nome}={texto!r} deveria ser um inteiro.") from None
    if valor <= 0:
        raise ErroConfig(f"{nome}={valor} deveria ser positivo.")
    return valor


def _escolha(ambiente: MutableMapping[str, str], nome: str, padrao: str,
             aceitos: tuple[str, ...]) -> str:
    valor = (ambiente.get(nome) or padrao).strip().lower()
    if valor not in aceitos:
        raise ErroConfig(
            f"{nome}={valor!r} nao e reconhecido; valores aceitos: "
            f"{', '.join(aceitos)}."
        )
    return valor


def ler_config(ambiente: MutableMapping[str, str] | None = None,
               *, usar_env_arquivo: bool = True) -> Config:
    """Monta a `Config` a partir do ambiente (e do `.env`, se houver)."""
    amb = os.environ if ambiente is None else ambiente
    if usar_env_arquivo:
        carregar_env(ambiente=amb)
    return Config(
        provedor=_escolha(amb, "RVGEN_PROVEDOR", "ollama", PROVEDORES),
        modelo=(amb.get("RVGEN_MODELO") or "").strip() or None,
        ollama_host=(amb.get("OLLAMA_HOST") or "").strip() or None,
        openrouter_key=(amb.get("OPENROUTER_API_KEY") or "").strip() or None,
        openrouter_url=(amb.get("RVGEN_OPENROUTER_URL") or OPENROUTER_URL).rstrip("/"),
        modelo_externo=(amb.get("SPECHDL_LLM_MODEL") or "").strip()
        or MODELO_EXTERNO_PADRAO,
        num_ctx=_int(amb, "RVGEN_NUM_CTX", 16384),
        temperatura=0.2,
        timeout_s=float(_int(amb, "RVGEN_TIMEOUT", 900)),
        executor=_escolha(amb, "RVGEN_EXECUTOR", "auto", EXECUTORES),
        imagem_docker=(amb.get("RVGEN_IMAGEM_DOCKER") or "").strip()
        or IMAGEM_DOCKER_PADRAO,
    )
