#!/usr/bin/env python3
"""Servidor HTTP local do app de iteracoes: a pagina e uma API JSON.

Seguranca (o servidor escreve em arquivos do repositorio):

- escuta so em 127.0.0.1;
- todo pedido precisa de ``Host`` local (contra DNS rebinding);
- POST exige o token aleatorio da partida no cabecalho ``X-Token``, corpo
  JSON e, se vier ``Origin``, que ele seja local (outro site nao consegue
  mandar POST para localhost em nome do usuario);
- corpo limitado a ``LIMITE_CORPO`` bytes;
- ids e caminhos de arquivo sao validados no nucleo.
"""

from __future__ import annotations

import hmac
import json
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .nucleo import ErroIteracoes, ErroNaoEncontrado, ErroPermissao, Repositorio

__all__ = ["ServidorIteracoes", "criar_servidor", "LIMITE_CORPO", "HOST"]

HOST = "127.0.0.1"
LIMITE_CORPO = 2 * 1024 * 1024
PAGINA = Path(__file__).with_name("app.html")
_MARCA_TOKEN = "__TOKEN_ITERACOES__"


class ServidorIteracoes(ThreadingHTTPServer):
    """``ThreadingHTTPServer`` com o repositorio e o token da sessao."""

    daemon_threads = True

    def __init__(self, repo: Repositorio, porta: int = 0, token: str | None = None) -> None:
        self.repo = repo
        self.token = token or secrets.token_urlsafe(32)
        self.trava = threading.Lock()       # pedidos em serie (arquivos pequenos)
        super().__init__((HOST, porta), Manipulador)

    @property
    def porta(self) -> int:
        return self.server_address[1]

    @property
    def url(self) -> str:
        return f"http://{HOST}:{self.porta}/"

    def hosts_aceitos(self) -> set[str]:
        return {f"{HOST}:{self.porta}", f"localhost:{self.porta}"}


def criar_servidor(raiz: Path | str, porta: int = 0, token: str | None = None) -> ServidorIteracoes:
    return ServidorIteracoes(Repositorio(raiz), porta, token)


class ErroHttp(Exception):
    def __init__(self, status: int, mensagem: str) -> None:
        super().__init__(mensagem)
        self.status = status


class Manipulador(BaseHTTPRequestHandler):
    server: ServidorIteracoes
    server_version = "iteracoes"
    sys_version = ""

    def log_message(self, formato: str, *args) -> None:   # silencioso
        pass

    # -- respostas ----------------------------------------------------------

    def _cabecalhos_comuns(self) -> None:
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _enviar(self, status: int, corpo: bytes, tipo: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(corpo)))
        self._cabecalhos_comuns()
        if tipo.startswith("text/html"):
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; script-src 'unsafe-inline'; "
                             "style-src 'unsafe-inline'; connect-src 'self'; img-src 'self' data:; "
                             "base-uri 'none'; form-action 'none'; frame-ancestors 'none'")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(corpo)

    def _json(self, status: int, dados: object) -> None:
        corpo = json.dumps(dados, ensure_ascii=False).encode("utf-8")
        self._enviar(status, corpo, "application/json; charset=utf-8")

    def _erro(self, status: int, mensagem: str) -> None:
        self._json(status, {"erro": mensagem})

    # -- checagens ----------------------------------------------------------

    def _checar_host(self) -> None:
        host = (self.headers.get("Host") or "").strip().lower()
        if host not in self.server.hosts_aceitos():
            raise ErroHttp(403, "Host não permitido: abra o app pelo endereço local.")

    def _checar_post(self) -> None:
        origem = self.headers.get("Origin")
        if origem is not None:
            o = urlsplit(origem.strip().lower())
            if o.scheme != "http" or o.netloc not in self.server.hosts_aceitos():
                raise ErroHttp(403, "Origin não permitida.")
        token = self.headers.get("X-Token") or ""
        if not hmac.compare_digest(token.encode("utf-8"), self.server.token.encode("utf-8")):
            raise ErroHttp(403, "token ausente ou inválido: recarregue a página do app.")
        tipo = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if tipo != "application/json":
            raise ErroHttp(415, "envie JSON (Content-Type: application/json).")

    def _ler_bruto(self) -> bytes:
        """Le o corpo inteiro (antes de recusar, para nao resetar a conexao)."""
        try:
            tamanho = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            raise ErroHttp(400, "Content-Length inválido.")
        if tamanho < 0:
            raise ErroHttp(400, "Content-Length inválido.")
        if tamanho > LIMITE_CORPO:
            self.close_connection = True
            raise ErroHttp(413, f"corpo grande demais (máx. {LIMITE_CORPO} bytes).")
        return self.rfile.read(tamanho) if tamanho else b"{}"

    @staticmethod
    def _decodificar(bruto: bytes) -> dict:
        try:
            dados = json.loads(bruto.decode("utf-8"))
        except (ValueError, RecursionError):
            # ValueError cobre UnicodeDecodeError, JSONDecodeError e inteiro
            # com digitos demais; RecursionError, aninhamento profundo
            raise ErroHttp(400, "JSON inválido.")
        if not isinstance(dados, dict):
            raise ErroHttp(400, "o corpo deve ser um objeto JSON.")
        return dados

    # -- despacho -----------------------------------------------------------

    def _tratar(self, metodo: str) -> None:
        try:
            self._checar_host()
            url = urlsplit(self.path)
            if metodo == "GET":
                consulta = {k: v[-1] for k, v in parse_qs(url.query).items()}
                with self.server.trava:     # nao le uma copia pela metade
                    self._get(url.path, consulta)
            else:
                bruto = self._ler_bruto()
                self._checar_post()
                dados = self._decodificar(bruto)
                with self.server.trava:
                    self._post(url.path, dados)
        except ErroHttp as e:
            self._erro(e.status, str(e))
        except ErroPermissao as e:
            self._erro(403, str(e))
        except ErroNaoEncontrado as e:
            self._erro(404, str(e))
        except ErroIteracoes as e:
            self._erro(400, str(e))
        except Exception as e:          # noqa: BLE001 -- o app mostra a mensagem
            self._erro(500, f"erro interno: {type(e).__name__}: {e}")

    def do_GET(self) -> None:
        self._tratar("GET")

    def do_HEAD(self) -> None:
        self._tratar("GET")

    def do_POST(self) -> None:
        self._tratar("POST")

    def _get(self, caminho: str, q: dict) -> None:
        repo = self.server.repo
        if caminho in ("/", "/index.html"):
            html = PAGINA.read_text(encoding="utf-8").replace(_MARCA_TOKEN, self.server.token)
            self._enviar(200, html.encode("utf-8"), "text/html; charset=utf-8")
        elif caminho == "/api/versoes":
            self._json(200, repo.listar())
        elif caminho == "/api/arquivos":
            versao = q.get("versao", "")
            self._json(200, {"versao": versao, "arquivos": repo.arquivos(versao),
                             "ausentes": repo.obrigatorios_ausentes(versao),
                             "pasta": repo.caminho_relativo_da_versao(versao)})
        elif caminho == "/api/arquivo":
            versao, rel = q.get("versao", ""), q.get("rel", "")
            self._json(200, {"versao": versao, "rel": rel,
                             "texto": repo.ler_arquivo(versao, rel)})
        elif caminho == "/api/analise":
            self._json(200, repo.analisar(q.get("versao", "")))
        elif caminho == "/api/prompt":
            self._json(200, repo.prompt(q.get("versao", "")))
        elif caminho == "/api/resumo":
            self._json(200, repo.resumo_diferencas(q.get("a", ""), q.get("b", "")))
        elif caminho == "/api/diff":
            self._json(200, repo.diff(q.get("a", ""), q.get("b", ""), q.get("rel", "")))
        elif caminho == "/api/experimento":
            self._json(200, repo.resultado_experimento(q.get("nome", "")))
        elif caminho == "/favicon.ico":
            self._enviar(204, b"", "image/x-icon")
        else:
            raise ErroHttp(404, f"rota inexistente: {caminho}")

    def _post(self, caminho: str, d: dict) -> None:
        repo = self.server.repo
        if caminho == "/api/iteracoes":
            it = repo.criar_iteracao(d.get("origem", "base"), d.get("nome", ""),
                                     d.get("notas", ""))
            self._json(201, {"id": it})
        elif caminho == "/api/iteracao":
            self._json(200, repo.atualizar_iteracao(d.get("id", ""), d.get("nome"),
                                                    d.get("notas")))
        elif caminho == "/api/arquivo":
            self._json(200, repo.salvar_arquivo(d.get("versao", ""), d.get("rel", ""),
                                                d.get("texto")))
        elif caminho == "/api/promover":
            self._json(200, repo.promover(d.get("id", "")))
        elif caminho == "/api/vincular":
            if d.get("remover"):
                meta = repo.desvincular_experimento(d.get("id", ""), d.get("nome", ""))
            else:
                meta = repo.vincular_experimento(d.get("id", ""), d.get("nome", ""))
            self._json(200, meta)
        else:
            raise ErroHttp(404, f"rota inexistente: {caminho}")
