"""Configuracao comum do pytest na raiz do repositorio.

``RVGEN_SPECS_DIR`` definida no terminal (o app de iteracoes sugere
``$env:RVGEN_SPECS_DIR=...``) faria a suite testar o contrato contra uma
iteracao. A suite sempre roda com ``specs/``; os testes que precisam da
variavel a definem e a removem sozinhos.
"""

import os


def pytest_configure(config):
    os.environ.pop("RVGEN_SPECS_DIR", None)
