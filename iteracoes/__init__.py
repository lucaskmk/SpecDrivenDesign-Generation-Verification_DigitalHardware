#!/usr/bin/env python3
"""iteracoes -- app local para iterar nas specs sem perder a base.

    python -m iteracoes              # sobe o servidor e abre o navegador
    python -m iteracoes --porta 8800 --sem-navegador

    iteracoes.nucleo     toda a logica (versoes, copia, diff, analise, promover)
    iteracoes.servidor   http.server + API JSON, so em 127.0.0.1
    iteracoes/app.html   a pagina (HTML/CSS/JS inline)

Os dados ficam aqui mesmo: ``base/specs`` (somente leitura) e uma pasta
``it-NNN/`` por iteracao. O app nunca roda o rvgen nem chama LLM: ele so
mostra o comando. Veja ``iteracoes/README.md``.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
