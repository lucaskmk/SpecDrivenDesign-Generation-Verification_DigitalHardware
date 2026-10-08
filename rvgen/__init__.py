#!/usr/bin/env python3
"""rvgen -- gerador de CPUs RISC-V por agente, com IA local ou externa.

O fluxo ativo está documentado em `specs/spec.md`.

O pacote inteiro existe para uma coisa: escrever uma entrega em
`entregas/<nome>/` e submete-la ao MESMO validador que julga a CPU de um
 aluno. Ele é cliente do `spec-riscv-test`, nunca o contrário: o validador não sabe
que o gerador existe, e um modelo de linguagem nunca julga a propria CPU.

    rvgen.config     .env, variaveis de ambiente e defaults
    rvgen.llm        cliente unico de LLM: Ollama (local) e OpenRouter (externo)
    rvgen.ollama     acha, instala, inicia e abastece o Ollama (`preparar`)
     rvgen.executor   roda `spec-riscv-test` no host
     rvgen.contrato   o contrato fixo da CPU
    rvgen.agente     o laco gerar -> validar -> corrigir

So a biblioteca padrao do Python: o gerador roda no host ou dentro da imagem
`spechdl-toolchain` sem instalar nenhum pacote.
"""

from __future__ import annotations

__all__ = ["__version__"]

__version__ = "0.1.0"
