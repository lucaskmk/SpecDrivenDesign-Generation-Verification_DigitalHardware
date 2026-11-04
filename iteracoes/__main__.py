#!/usr/bin/env python3
"""``python -m iteracoes``: sobe o app de iteracoes de specs e abre o navegador."""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

from .servidor import criar_servidor

RAIZ = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m iteracoes",
        description="App local para ver, analisar, editar e comparar versoes das specs.")
    p.add_argument("--porta", type=int, default=8765,
                   help="porta local (padrao 8765; 0 escolhe uma livre)")
    p.add_argument("--sem-navegador", action="store_true",
                   help="nao abre o navegador, so mostra o endereco")
    args = p.parse_args(argv)
    if not 0 <= args.porta <= 65535:
        print("ERRO: --porta deve estar entre 0 e 65535", file=sys.stderr)
        return 2
    try:
        servidor = criar_servidor(RAIZ, args.porta)
    except OSError as e:
        print(f"ERRO: nao foi possivel abrir a porta {args.porta}: {e}\n"
              f"Ja tem um app aberto? Tente: python -m iteracoes --porta {args.porta + 1}",
              file=sys.stderr)
        return 1
    print(f"iteracoes: app em {servidor.url}")
    print("  base    : iteracoes/base/specs (somente leitura)")
    print("  ativa   : specs/ (o que o rvgen le por padrao)")
    print("  Ctrl-C para encerrar.", flush=True)
    if not args.sem_navegador:
        threading.Timer(0.5, webbrowser.open, (servidor.url,)).start()
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nencerrado.")
    finally:
        servidor.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
