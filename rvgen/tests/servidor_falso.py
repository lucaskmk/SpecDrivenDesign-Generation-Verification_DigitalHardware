#!/usr/bin/env python3
"""Servidor HTTP falso para os testes do gerador -- sem rede, sem Ollama.

Sobe um `ThreadingHTTPServer` em 127.0.0.1, numa porta livre, e responde
por rota com funcoes definidas pelo teste. Guarda cada requisicao recebida
(metodo, caminho, cabecalhos e corpo JSON) para o teste conferir o que o
cliente realmente mandou.

Uma rota devolve `(status, corpo)`, onde `corpo` e um dict (vira JSON) ou
uma lista de dicts (vira JSON Lines, o streaming do Ollama).
"""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

Rota = Callable[[dict | None, dict[str, str]], tuple[int, Any]]


class ServidorFalso:
    def __init__(self, rotas: dict[tuple[str, str], Rota]) -> None:
        self.rotas = rotas
        self.recebidas: list[dict] = []
        servidor = self

        class Handler(BaseHTTPRequestHandler):
            def _responder(self, metodo: str) -> None:
                tamanho = int(self.headers.get("Content-Length") or 0)
                bruto = self.rfile.read(tamanho) if tamanho else b""
                corpo = json.loads(bruto) if bruto else None
                cabecalhos = {k.lower(): v for k, v in self.headers.items()}
                servidor.recebidas.append({"metodo": metodo, "caminho": self.path,
                                           "cabecalhos": cabecalhos, "corpo": corpo})
                rota = servidor.rotas.get((metodo, self.path))
                if rota is None:
                    status, resposta = 404, {"error": f"rota {self.path} inexistente"}
                else:
                    status, resposta = rota(corpo, cabecalhos)
                if isinstance(resposta, list):
                    dados = "".join(json.dumps(x) + "\n" for x in resposta).encode()
                    tipo = "application/x-ndjson"
                else:
                    dados = json.dumps(resposta).encode()
                    tipo = "application/json"
                self.send_response(status)
                self.send_header("Content-Type", tipo)
                self.send_header("Content-Length", str(len(dados)))
                self.end_headers()
                self.wfile.write(dados)

            def do_GET(self) -> None:  # noqa: N802
                self._responder("GET")

            def do_POST(self) -> None:  # noqa: N802
                self._responder("POST")

            def log_message(self, *args: Any) -> None:
                pass

        self._http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._http.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, porta = self._http.server_address[:2]
        return f"http://{host}:{porta}"

    def __enter__(self) -> "ServidorFalso":
        self._thread.start()
        return self

    def __exit__(self, *exc: Any) -> None:
        self._http.shutdown()
        self._http.server_close()
