#!/usr/bin/env python3
"""Gerador de CPUs RISC-V por agente -- ponto de entrada.

REQ: FR-RV-43, FR-RV-44, FR-RV-45, FR-RV-46.

    python -m rvgen preparar              confere Ollama, modelo e executor;
                                          oferece instalar/baixar o que faltar
    python -m rvgen preparar --verificar  so confere, nao muda nada
    python -m rvgen preparar --sim        responde "sim" a toda confirmacao

Codigo de saida: 0 quando tudo esta pronto, 1 com pendencia, 2 com erro de
uso ou de configuracao.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

from . import executor as ex
from . import ollama as ol
from .config import ErroConfig, ler_config

VERDE = "\033[32m"
VERMELHO = "\033[31m"
AMARELO = "\033[33m"
CINZA = "\033[90m"
FIM = "\033[0m"


class Tela:
    """Uma linha por item, no estilo do relatorio do rvverify."""

    def __init__(self, cor: bool) -> None:
        self.cor = cor

    def _c(self, texto: str, tom: str) -> str:
        return f"{tom}{texto}{FIM}" if self.cor else texto

    def ok(self, texto: str) -> None:
        print(f"  {self._c('ok   ', VERDE)}  {texto}", flush=True)

    def falta(self, texto: str, resolver: str | None = None) -> None:
        print(f"  {self._c('FALTA', VERMELHO)}  {texto}", flush=True)
        if resolver:
            print(f"         {self._c('resolver: ' + resolver, CINZA)}", flush=True)

    def info(self, texto: str) -> None:
        print(f"  {self._c('info ', AMARELO)}  {texto}", flush=True)


def _progresso_download(interativo: bool):
    """Barra de download do modelo; sem terminal, so as mudancas de estado."""
    ultimo = {"status": None, "pct": -1}

    def mostrar(status: str, feito: int | None, total: int | None) -> None:
        if feito and total:
            pct = int(100 * feito / total)
            if interativo:
                print(f"\r         {status[:28]:<28} {pct:3d}%  "
                      f"({feito / 1e9:.2f}/{total / 1e9:.2f} GB)", end="", flush=True)
            elif pct // 10 != ultimo["pct"] // 10:
                print(f"         {pct}% ({feito / 1e9:.2f}/{total / 1e9:.2f} GB)", flush=True)
            ultimo["pct"] = pct
        elif status != ultimo["status"]:
            if interativo and ultimo["pct"] >= 0:
                print()
            print(f"         {status}", flush=True)
            ultimo["pct"] = -1
        ultimo["status"] = status
    return mostrar


def _interativo() -> bool:
    """Ha alguem no terminal para responder uma confirmacao?"""
    return sys.stdin is not None and sys.stdin.isatty()


def cmd_preparar(args: argparse.Namespace) -> int:
    try:
        cfg = ler_config()
    except ErroConfig as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    interativo = _interativo()
    tela = Tela(cor=not args.sem_cor and sys.stdout.isatty())

    def confirmar(pergunta: str) -> bool:
        """FR-RV-44: nada e instalado nem baixado sem um sim explicito."""
        if args.verificar:
            return False
        if args.sim:
            return True
        if not interativo:
            tela.info("sem terminal interativo e sem --sim: nada sera instalado")
            return False
        resposta = input(f"         {pergunta} [s/N] ").strip().lower()
        return resposta in ("s", "sim", "y", "yes")

    modo = "so verificacao, nada sera alterado" if args.verificar else \
        "pergunta antes de instalar ou baixar"
    print(f"rvgen preparar -- o que o gerador precisa para rodar local ({modo})\n")
    pendencias = 0

    # -- 1. Ollama: servidor, executavel, instalacao ----------------------
    candidatos = ol.hosts_candidatos()
    servidor = ol.localizar_servidor(candidatos)
    binario = ol.localizar_binario()
    if servidor is None and binario is None:
        plano = ol.plano_de_instalacao()
        tela.falta("Ollama nao esta instalado", plano.manual or plano.descricao)
        if plano.manual is None and confirmar(f"Instalar o Ollama agora ({plano.descricao})?"):
            try:
                codigo = ol.executar_plano(plano)
            except ol.ErroOllama as e:
                codigo = 1
                tela.falta(f"a instalacao falhou: {e}")
            binario = ol.localizar_binario()
            if codigo == 0 and binario:
                tela.ok(f"Ollama instalado em {binario}")
                servidor = ol.localizar_servidor(candidatos)
            else:
                tela.falta(f"o instalador terminou com codigo {codigo} e o "
                           f"executavel nao foi encontrado", ol.URL_DOWNLOAD)
                pendencias += 1
        else:
            pendencias += 1
    elif binario is not None:
        tela.ok(f"Ollama instalado em {binario}")

    if servidor is None and binario is not None:
        # o `ollama serve` escuta em OLLAMA_HOST, se definido -- o primeiro candidato
        base_local = candidatos[0]
        if args.verificar:
            tela.falta("o servidor Ollama nao responde",
                       f'"{binario}" serve   (ou abra o app do Ollama)')
            pendencias += 1
        else:
            log = Path(tempfile.gettempdir()) / "rvgen-ollama-serve.log"
            tela.info(f"iniciando `ollama serve` em segundo plano (log: {log})")
            v = ol.iniciar_servidor(binario, log, base=base_local)
            if v:
                servidor = (base_local, v)
            else:
                tela.falta("o servidor nao respondeu em 30 s", f"veja o log {log}")
                pendencias += 1
    if servidor is not None:
        base, versao = servidor
        tela.ok(f"servidor Ollama {versao} em {base}")

    # -- 2. modelo ---------------------------------------------------------
    try:
        modelo, origem = ol.resolver_modelo(args.modelo, args.perfil, cfg.modelo)
    except ol.ErroOllama as e:
        print(f"ERRO: {e}", file=sys.stderr)
        return 2
    if servidor is None:
        tela.falta(f"modelo {modelo} ({origem}): nao verificado, sem servidor Ollama")
        pendencias += 1
    else:
        base = servidor[0]
        try:
            instalados = ol.modelos_instalados(base)
        except ol.ErroOllama as e:
            instalados = []
            tela.falta(str(e))
        if ol.tem_modelo(instalados, modelo):
            tela.ok(f"modelo {modelo} ({origem})")
        else:
            tamanho = ol.tamanho_remoto(modelo)
            txt = f"{tamanho / 1e9:.2f} GB" if tamanho else "tamanho desconhecido"
            tela.falta(f"modelo {modelo} nao esta baixado ({origem})",
                       f"python -m rvgen preparar --modelo {modelo}   ({txt})")
            if confirmar(f"Baixar {modelo} agora ({txt}, de registry.ollama.ai)?"):
                try:
                    ol.baixar_modelo(base, modelo, _progresso_download(interativo))
                    if interativo:
                        print()
                    tela.ok(f"modelo {modelo} baixado")
                except ol.ErroOllama as e:
                    print()
                    tela.falta(str(e))
                    pendencias += 1
            else:
                pendencias += 1

    # -- 3. onde o rvverify roda ------------------------------------------
    pref = args.executor or cfg.executor
    checagens = []
    if pref in ("auto", "local"):
        checagens.append(("local", ex.checar_local()))
    if pref in ("auto", "docker"):
        checagens.append(("docker", ex.checar_docker(cfg.imagem_docker)))
    prontos = [(n, d) for n, d in checagens if d.pronto]
    if prontos:
        nome, d = prontos[0]
        tela.ok(f"executor do rvverify: {nome} -- {d.detalhe}")
    else:
        for nome, d in checagens:
            tela.falta(f"executor {nome} do rvverify: {d.detalhe}", d.como_resolver)
        pendencias += 1

    # -- 4. provedor externo (so informacao) ------------------------------
    if cfg.openrouter_key:
        tela.info(f"OPENROUTER_API_KEY definida: --provedor openrouter disponivel "
                  f"(modelo padrao {cfg.modelo_externo})")
    else:
        tela.info("OPENROUTER_API_KEY nao definida: so necessaria com --provedor openrouter")

    print()
    if pendencias:
        print(f"{pendencias} pendencia(s). Resolva as linhas FALTA acima e rode de novo.")
        return 1
    print("Tudo pronto. Proximo passo:\n"
          "  python -m rvgen gerar entregas/<nome> --tipo monociclo --isa rv32im")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m rvgen",
        description="Gera CPUs RISC-V com um agente de IA local (Ollama) ou "
                    "externo (OpenRouter) e as valida com o rvverify.",
    )
    sub = ap.add_subparsers(dest="comando", required=True)

    p = sub.add_parser("preparar", help="confere e prepara Ollama, modelo e executor")
    p.add_argument("--verificar", action="store_true",
                   help="so confere; nao instala, nao baixa, nao inicia nada")
    p.add_argument("--sim", action="store_true",
                   help="responde sim a toda confirmacao (para scripts)")
    p.add_argument("--modelo", help="modelo do Ollama (padrao: perfil pela VRAM)")
    p.add_argument("--perfil", choices=["auto", *ol.PERFIS], default=None,
                   help="perfil de modelo local (padrao: auto)")
    p.add_argument("--executor", choices=["auto", "local", "docker"], default=None,
                   help="onde rodar o rvverify (padrao: auto)")
    p.add_argument("--sem-cor", action="store_true", help="saida sem cor ANSI")
    p.set_defaults(func=cmd_preparar)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
