#!/usr/bin/env python3
"""rvgen -- gerador de CPUs RISC-V por agente, com IA local ou externa.

REQ: FR-RV-43 a FR-RV-50, NFR-RV-07 (ver `specs/spec.md` e ADR-018).

O pacote inteiro existe para uma coisa: escrever uma entrega em
`entregas/<nome>/` e submete-la ao MESMO validador que julga a CPU de um
aluno. Ele e cliente do `rvverify`, nunca o contrario: o validador nao sabe
que o gerador existe, e um modelo de linguagem nunca julga a propria CPU.

    rvgen.config     .env, variaveis de ambiente e defaults
    rvgen.llm        cliente unico de LLM: Ollama (local) e OpenRouter (externo)
    rvgen.ollama     acha, instala, inicia e abastece o Ollama (`preparar`)
    rvgen.executor   roda `python -m rvverify` no host ou no Docker
    rvgen.contrato   o que cada tipo de CPU precisa cumprir e o `cpu.toml`
    rvgen.agente     o laco gerar -> validar -> corrigir

So a biblioteca padrao do Python: o gerador roda no host ou dentro da imagem
`spechdl-toolchain` sem instalar nenhum pacote.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
