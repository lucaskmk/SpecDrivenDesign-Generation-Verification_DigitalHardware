#!/usr/bin/env python3
"""Cliente unico de LLM: Ollama (local) e OpenRouter (externo).

REQ: FR-RV-46 (dois provedores intercambiaveis por configuracao, so com a
biblioteca padrao), FR-RV-50 (tokens e duracao de cada chamada registrados).

Os dois clientes tem a mesma forma -- `conversar(mensagens, schema=None)`
devolve uma `Resposta` -- e o agente nao sabe qual deles esta usando. As
diferencas ficam aqui dentro:

  * `ClienteOllama` fala a API NATIVA (`/api/chat`), e nao a compativel com
    OpenAI, por dois motivos: so a nativa aceita `options.num_ctx` (o padrao
    do Ollama e pequeno demais para contrato + arquivo + diagnostico), e so
    ela restringe a saida a um JSON Schema (`format`), o que faz um modelo
    local de 7B devolver JSON valido sempre. A resposta vem em streaming,
    para a tela nao ficar muda durante minutos.
  * `ClienteOpenAI` fala Chat Completions (`/chat/completions`) -- o formato
    do OpenRouter e de qualquer servidor compativel. O schema, quando pedido,
    vai no texto do prompt pelo agente; aqui ele nao e enviado, porque nem
    todo modelo roteado pelo OpenRouter aceita `response_format`.

Nenhuma dependencia: so `urllib`. A ADR-018 registra por que isso substitui
o SDK `openrouter` no gerador.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable, Iterator

__all__ = [
    "ErroLLM",
    "Resposta",
    "ClienteOllama",
    "ClienteOpenAI",
    "extrair_json",
    "extrair_vhdl",
]

Mensagens = list[dict[str, str]]
Progresso = Callable[[int], None]


class ErroLLM(RuntimeError):
    """A chamada ao modelo falhou, ou a resposta nao tem o formato pedido."""


@dataclass(frozen=True)
class Resposta:
    """Uma resposta do modelo, com o que for medido pelo provedor."""

    texto: str
    provedor: str
    modelo: str
    tokens_entrada: int | None
    tokens_saida: int | None
    segundos: float


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------

def _mensagem_de_erro(e: urllib.error.HTTPError) -> str:
    """O motivo que o SERVIDOR deu, nao so o codigo HTTP."""
    try:
        corpo = e.read().decode("utf-8", errors="replace")
    except Exception:                                      # noqa: BLE001
        corpo = ""
    finally:
        e.close()
    try:
        dados = json.loads(corpo)
        erro = dados.get("error", dados)
        if isinstance(erro, dict):
            erro = erro.get("message") or json.dumps(erro, ensure_ascii=False)
        return f"HTTP {e.code}: {erro}"
    except (ValueError, AttributeError):
        return f"HTTP {e.code}: {corpo.strip()[:300] or e.reason}"


def _requisicao(url: str, corpo: dict, headers: dict[str, str] | None) -> urllib.request.Request:
    dados = json.dumps(corpo).encode("utf-8")
    cabecalhos = {"Content-Type": "application/json"}
    cabecalhos.update(headers or {})
    return urllib.request.Request(url, data=dados, headers=cabecalhos, method="POST")


def post_json(url: str, corpo: dict, *, headers: dict[str, str] | None = None,
              timeout: float = 60.0) -> dict:
    """POST com corpo JSON, resposta JSON."""
    try:
        with urllib.request.urlopen(_requisicao(url, corpo, headers),
                                    timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise ErroLLM(f"{url}: {_mensagem_de_erro(e)}") from None
    except urllib.error.URLError as e:
        raise ErroLLM(f"{url}: sem conexao ({e.reason})") from None
    except (TimeoutError, OSError) as e:
        raise ErroLLM(f"{url}: {e}") from None
    except ValueError as e:
        raise ErroLLM(f"{url}: resposta nao e JSON ({e})") from None


def post_linhas_json(url: str, corpo: dict, *, timeout: float = 60.0) -> Iterator[dict]:
    """POST cuja resposta e JSON Lines (o streaming do Ollama)."""
    try:
        with urllib.request.urlopen(_requisicao(url, corpo, None),
                                    timeout=timeout) as r:
            for bruta in r:
                linha = bruta.decode("utf-8").strip()
                if linha:
                    yield json.loads(linha)
    except urllib.error.HTTPError as e:
        raise ErroLLM(f"{url}: {_mensagem_de_erro(e)}") from None
    except urllib.error.URLError as e:
        raise ErroLLM(f"{url}: sem conexao ({e.reason})") from None
    except (TimeoutError, OSError) as e:
        raise ErroLLM(f"{url}: {e}") from None
    except ValueError as e:
        raise ErroLLM(f"{url}: linha de resposta nao e JSON ({e})") from None


# --------------------------------------------------------------------------
# clientes
# --------------------------------------------------------------------------

class ClienteOllama:
    """Modelo local servido pelo Ollama."""

    provedor = "ollama"

    def __init__(self, base: str, modelo: str, *, num_ctx: int = 16384,
                 temperatura: float = 0.2, timeout: float = 900.0,
                 ao_progredir: Progresso | None = None) -> None:
        self.base = base.rstrip("/")
        self.modelo = modelo
        self.num_ctx = num_ctx
        self.temperatura = temperatura
        self.timeout = timeout
        self.ao_progredir = ao_progredir

    def conversar(self, mensagens: Mensagens, *,
                  schema: dict | None = None) -> Resposta:
        corpo: dict[str, Any] = {
            "model": self.modelo,
            "messages": mensagens,
            "stream": True,
            "options": {"num_ctx": self.num_ctx, "temperature": self.temperatura},
        }
        if schema is not None:
            corpo["format"] = schema
        inicio = time.monotonic()
        partes: list[str] = []
        total = 0
        final: dict = {}
        for evento in post_linhas_json(f"{self.base}/api/chat", corpo,
                                       timeout=self.timeout):
            if evento.get("error"):
                raise ErroLLM(f"ollama ({self.modelo}): {evento['error']}")
            pedaco = (evento.get("message") or {}).get("content") or ""
            if pedaco:
                partes.append(pedaco)
                total += len(pedaco)
                if self.ao_progredir:
                    self.ao_progredir(total)
            if evento.get("done"):
                final = evento
        if not final:
            raise ErroLLM(f"ollama ({self.modelo}): a resposta terminou sem `done`.")
        return Resposta(
            texto="".join(partes),
            provedor=self.provedor,
            modelo=self.modelo,
            tokens_entrada=final.get("prompt_eval_count"),
            tokens_saida=final.get("eval_count"),
            segundos=round(time.monotonic() - inicio, 2),
        )


class ClienteOpenAI:
    """Modelo externo por Chat Completions -- OpenRouter por padrao."""

    provedor = "openrouter"

    def __init__(self, base_url: str, chave: str | None, modelo: str, *,
                 temperatura: float = 0.2, timeout: float = 900.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.chave = chave
        self.modelo = modelo
        self.temperatura = temperatura
        self.timeout = timeout

    def conversar(self, mensagens: Mensagens, *,
                  schema: dict | None = None) -> Resposta:
        del schema  # ver a docstring do modulo: vai no prompt, nao na API
        if not self.chave:
            raise ErroLLM(
                "OPENROUTER_API_KEY nao definida. Copie .env.example para .env "
                "e preencha a chave, ou use --provedor ollama."
            )
        headers = {
            "Authorization": f"Bearer {self.chave}",
            # identificacao opcional pedida pelo OpenRouter
            "X-Title": "rvgen",
        }
        corpo = {"model": self.modelo, "messages": mensagens,
                 "temperature": self.temperatura}
        inicio = time.monotonic()
        dados = post_json(f"{self.base_url}/chat/completions", corpo,
                          headers=headers, timeout=self.timeout)
        if dados.get("error"):
            erro = dados["error"]
            raise ErroLLM(f"openrouter ({self.modelo}): "
                          f"{erro.get('message') if isinstance(erro, dict) else erro}")
        try:
            texto = dados["choices"][0]["message"]["content"] or ""
        except (KeyError, IndexError, TypeError):
            raise ErroLLM(f"openrouter ({self.modelo}): resposta sem "
                          f"choices[0].message.content") from None
        uso = dados.get("usage") or {}
        return Resposta(
            texto=texto,
            provedor=self.provedor,
            modelo=dados.get("model") or self.modelo,
            tokens_entrada=uso.get("prompt_tokens"),
            tokens_saida=uso.get("completion_tokens"),
            segundos=round(time.monotonic() - inicio, 2),
        )


# --------------------------------------------------------------------------
# extracao do que interessa numa resposta
# --------------------------------------------------------------------------

_CERCA_RE = re.compile(r"```[ \t]*([A-Za-z0-9_+-]*)[^\n]*\n(.*?)```", re.DOTALL)


def extrair_json(texto: str) -> Any:
    """O JSON de uma resposta, mesmo com texto ou cerca de codigo em volta."""
    bruto = texto.strip()
    try:
        return json.loads(bruto)
    except ValueError:
        pass
    for linguagem, corpo in _CERCA_RE.findall(bruto):
        if linguagem.lower() in ("json", ""):
            try:
                return json.loads(corpo)
            except ValueError:
                continue
    inicio, fim = bruto.find("{"), bruto.rfind("}")
    if 0 <= inicio < fim:
        try:
            return json.loads(bruto[inicio:fim + 1])
        except ValueError:
            pass
    raise ErroLLM("a resposta do modelo nao contem JSON valido.")


def extrair_vhdl(texto: str) -> str | None:
    """O arquivo VHDL de uma resposta: o maior bloco cercado como vhdl.

    Sem cerca nenhuma, aceita a resposta inteira se ela parecer um arquivo
    VHDL (tem `entity` e `architecture`). Devolve None quando nao ha VHDL.
    """
    blocos = [corpo for linguagem, corpo in _CERCA_RE.findall(texto)
              if linguagem.lower() in ("vhdl", "vhd", "")]
    candidatos = [b for b in blocos if re.search(r"\bentity\b", b, re.IGNORECASE)]
    if candidatos:
        return max(candidatos, key=len).strip() + "\n"
    if "```" not in texto and re.search(r"\bentity\b", texto, re.IGNORECASE) \
            and re.search(r"\barchitecture\b", texto, re.IGNORECASE):
        return texto.strip() + "\n"
    return None
